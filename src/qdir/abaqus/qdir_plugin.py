"""Abaqus CAE plugin to interact with qdir Queue"""

from __future__ import print_function, with_statement

__version__ = "1.0.0"
__author__ = "Carl Osterwisch"
__url__ = "https://github.com/costerwi/qdir/"

import json
import os
from subprocess import PIPE, Popen

from abaqusGui import *

if isinstance(u"unicode", str):

    def a(unicodeString):
        "Do nothing for Python3, Abaqus >=2024"
        return unicodeString
else:

    def a(unicodeString):
        "Convert unicode to str for Abaqus <2024"
        return unicodeString.encode("ascii", "ignore")


class QDirQueueMonitor(AFXDataDialog):
    (ID_TABLE, ID_REFRESH, ID_HELP, ID_SUBMITALL, ID_LAST) = range(
        AFXDataDialog.ID_LAST, AFXDataDialog.ID_LAST + 5
    )

    def __init__(self, form):
        AFXDataDialog.__init__(
            self,
            form,
            title="QDir Job Queue Monitor",
            opts=DIALOG_NORMAL | DECOR_RESIZE,
        )
        self.appendActionButton("Queue all Jobs", self, self.ID_SUBMITALL)
        FXMAPFUNC(self, SEL_COMMAND, self.ID_SUBMITALL, QDirQueueMonitor.submitAll)
        self.appendActionButton("Help", self, self.ID_HELP)
        FXMAPFUNC(self, SEL_COMMAND, self.ID_HELP, QDirQueueMonitor.getHelp)
        self.appendActionButton(self.DISMISS)
        self.updateTimer = None
        self.headings = ("jobId", "status", "name")
        self.jobData = {}

        sp = FXSplitter(self, LAYOUT_FILL_X | LAYOUT_FILL_Y | SPLITTER_VERTICAL)
        self.table = AFXTable(
            p=sp,
            numVisRows=6,
            numVisColumns=len(self.headings),
            numRows=1,
            numColumns=len(self.headings),
            tgt=self,
            sel=self.ID_TABLE,
            opts=AFXTABLE_NORMAL | AFXTABLE_ROW_MODE,
        )
        FXMAPFUNC(self, SEL_SELECTED, self.ID_TABLE, QDirQueueMonitor.onSelected)
        FXMAPFUNC(self, SEL_DELETED, self.ID_TABLE, QDirQueueMonitor.onDelete)
        self.table.setLeadingRows(numRows=1)
        self.table.setLeadingRowLabels("\t".join([h.title() for h in self.headings]))
        self.table.setColumnWidth(column=0, width=0)  # Hide the jobIds
        self.table.setColumnWidthInChars(column=1, numChars=30)
        self.table.setStretchableColumn(
            len(self.headings) - 1
        )  # Expand name as necessary
        self.table.setPopupOptions(AFXTable.POPUP_DELETE_ROW)
        self.jobDetails = FXText(p=sp, opts=TEXT_READONLY | LAYOUT_FILL_Y)
        self.jobDetails.setVisRows(5)
        try:
            self.interval = max(1, int(os.environ.get("QDIR_POLL_INTERVAL", "5")))
        except ValueError:
            self.interval = 5
        FXMAPFUNC(self, SEL_TIMEOUT, self.ID_REFRESH, QDirQueueMonitor.updateTable)

    def qstat(self):
        """Collect jobInfo of currently queued jobs"""
        self.jobData.clear()
        cmd = ["qstat", "--json"]
        env = os.environ.copy()
        env["PYTHONPATH"] = ""  # remove Abaqus modified PYTHONPATH
        try:
            process = Popen(cmd, stdout=PIPE, stderr=PIPE, env=env)
            stdout, stderr = process.communicate()
            returncode = process.returncode
        except OSError as e:
            returncode = "OSError"
            stdout = ""
            stderr = str(e)
        if returncode:
            # report error data
            jobInfo = {
                "status": "Error {}".format(returncode),
                "name": " ".join(cmd),
                "stdout": stdout,
                "stderr": stderr,
            }
            self.jobData["1"] = "1", jobInfo
        else:
            queuedJobs = json.loads(stdout)
            for qFilePath, jobInfo in queuedJobs.items():
                self.jobData[jobInfo["jobId"]] = qFilePath, jobInfo

    def detailedText(self, jobInfo):
        """Summarize full job status"""
        h = []
        for key, value in jobInfo.items():
            if "status" == key:
                continue
            if not value:
                continue
            if isinstance(value, list):
                h.append(key.upper())
                h.extend(value)
            else:
                h.append("{}\t{}".format(key.upper(), value))
        return "\n".join(h)

    def updateTable(self, *args):
        """Update manager with list of currently queued jobs"""
        row = self.table.getCurrentRow()
        if row < 1:
            selected = None  # nothing is selected
        else:
            selected = self.table.getItemText(row, column=0)
        self.qstat()
        diff = len(self.jobData) + 1 - self.table.getNumRows()
        if diff < 0:
            self.table.deleteRows(
                startRow=1,
                numRows=-diff,
                notify=FALSE,  # delete from top
            )
        elif diff > 0:
            self.table.insertRows(
                startRow=self.table.getNumRows(),  # add to bottom
                numRows=diff,
                notify=FALSE,
            )
        jobDetails = ""
        for row, (qFilePath, jobInfo) in enumerate(self.jobData.values(), 1):
            for column, heading in enumerate(self.headings):
                self.table.setItemValue(
                    row=row,
                    column=column,
                    valueText=a(jobInfo.get(heading, "")),
                )
            if jobInfo["jobId"] == selected or (selected is None and row == 1):
                jobDetails = self.detailedText(jobInfo)
        self.jobDetails.setText(a(jobDetails))
        self.updateTimer = getAFXApp().addTimeout(
            1000 * self.interval, self, self.ID_REFRESH
        )

    def onSelected(self, sender, sel, ptr):
        """Show the details for selected job"""
        row = sender.getCurrentRow()
        if row > 0:
            selected = self.table.getItemText(row, column=0)
            _qFilePath, jobInfo = self.jobData.get(selected, ("", {}))
            jobDetails = self.detailedText(jobInfo)
            self.jobDetails.setText(a(jobDetails))

    def onDelete(self, sender, sel, ptr):
        """Dequeue jobs for selected table rows"""
        cmd = ["qdel"]
        cmd.extend(
            self.table.getItemText(row, column=0)
            for row in range(1, self.table.getNumRows())
            if self.table.isRowSelected(row)
        )
        if len(cmd) > 1:
            self.jobDetails.setText("")
            env = os.environ.copy()
            env["PYTHONPATH"] = ""  # remove Abaqus modified PYTHONPATH
            process = Popen(cmd, env=env)
            process.wait()

    def submitAll(self, sender, sel, ptr):
        """Submit all CAE jobs"""
        sendCommand("qdir_submit.submitCAEJobs()")
        return 1

    def getHelp(self, sender, sel, ptr):
        """Open webbrowser to plugin helpUrl"""
        import webbrowser

        webbrowser.open(__url__)
        return 1

    def show(self):
        """Update the job data"""
        AFXDataDialog.show(self)
        self.updateTable()  # update the table and start the updateTimer

    def hide(self):
        """Remove the updateTimer"""
        if self.updateTimer is not None:
            getAFXApp().removeTimeout(self.updateTimer)
            self.updateTimer = None
        AFXDataDialog.hide(self)


class QDirForm(AFXForm):
    def getFirstDialog(self):
        return QDirQueueMonitor(self)


###########################################################################
# Register the plugin
###########################################################################
toolset = getAFXApp().getAFXMainWindow().getPluginToolset()

toolset.registerGuiMenuButton(
    buttonText="&QDir Job Queue Monitor...",
    object=QDirForm(toolset),
    kernelInitString="import qdir_submit # {}".format(__version__),
    author=__author__,
    version=str(__version__),
    helpUrl=__url__,
    description="Check status of jobs in the QDir Queue",
)
