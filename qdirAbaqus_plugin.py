"""Abaqus CAE plugin to interact with qdir Queue

Carl Osterwisch, August 2026
"""

from __future__ import print_function, with_statement

__version__ = "1.0.0"
__author__ = "Carl Osterwisch"
__url__ = "https://github.com/costerwi/qdir/"

import os
import sys
from textwrap import dedent
from abaqusGui import *

try:
    import qdir
except ImportError:
    qdir = None
except SyntaxError:
    qdir = None
    if sys.version_info.major >= 3:
        raise

installDir = os.path.dirname(os.path.normpath(__file__))
configExample = dedent(
    """
    import sys
    sys.path.append(r'{path}')
    import qdirAbaqus
    qdirAbaqus.init(queues)
    run_mode = BATCH
    """
).format(path=installDir)


class QDirQueueMonitor(AFXDataDialog):
    (ID_TABLE, ID_REFRESH, ID_LAST) = range(
        AFXDataDialog.ID_LAST, AFXDataDialog.ID_LAST + 3
    )

    def __init__(self, form):
        AFXDataDialog.__init__(
            self,
            form,
            title="QDir Job Queue Monitor",
            actionButtonIds=self.DISMISS,
            opts=DIALOG_NORMAL | DECOR_RESIZE,
        )
        self.updateTimer = None
        self.headings = ("jobId", "status", "name")
        self.jobData = {}

        sp = FXSplitter(self, LAYOUT_FILL_X | LAYOUT_FILL_Y | SPLITTER_VERTICAL)
        self.table = AFXTable(
            p=sp,
            numVisRows=5,
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
        self.interval = 10
        if qdir is not None:
            self.queue = qdir.Queue()
            self.interval = 1000 * qdir.default.interval  # ms between updates
            FXMAPFUNC(self, SEL_TIMEOUT, self.ID_REFRESH, QDirQueueMonitor.updateTable)

    def qstat(self):
        """Collect jobInfo of currently queued jobs"""
        self.jobData.clear()
        if qdir is None:
            return
        queuedJobs = self.queue.getQueuedJobs()
        for qFilePath in queuedJobs:
            jobInfo = qdir.getJobInfo(qFilePath)
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
                startRow=1, numRows=-diff, notify=FALSE  # delete from top
            )
        elif diff > 0:
            self.table.insertRows(
                startRow=self.table.getNumRows(),  # add to bottom
                numRows=diff,
                notify=FALSE,
            )
        if len(self.jobData) > 0:
            jobDetails = ""
        else:
            h = []
            if qdir:
                h.append("The job queue is empty.")
                if "qdir" in session.queues:
                    h.append(
                        'Submit jobs to it by first selecting qdir in the "Run Mode" for the Job.'
                    )
                else:
                    env = os.path.expanduser("~/abaqus_v6.env")
                    h.extend(
                        [
                            "Abaqus CAE is not yet configured to submit jobs to the queue.",
                            "Add the following lines to {} and restart CAE:".format(
                                env
                            ),
                            configExample,
                        ]
                    )
            else:
                # qdir failed to import
                required = "qdir.py", "qdirAbaqus.py"
                if sys.version_info.major < 3:
                    h.append("This queue monitor requires Abaqus CAE >= 2024")
                elif not all(
                    [os.path.exists(os.path.join(installDir, fn)) for fn in required]
                ):
                    h.append(
                        "You have an incomplete installation in {}".format(installDir)
                    )
                else:
                    h.append("qdir did not load correctly")
            jobDetails = "\n".join(h)

        for row, (qFilePath, jobInfo) in enumerate(self.jobData.values(), 1):
            for column, heading in enumerate(self.headings):
                self.table.setItemValue(
                    row=row,
                    column=column,
                    valueText=jobInfo.get(heading, ""),
                )
            if jobInfo["jobId"] == selected:
                jobDetails = self.detailedText(jobInfo)
        self.jobDetails.setText(jobDetails)
        self.updateTimer = getAFXApp().addTimeout(self.interval, self, self.ID_REFRESH)

    def onSelected(self, sender, sel, ptr):
        """Show the details for selected job"""
        row = sender.getCurrentRow()
        if row > 0:
            selected = self.table.getItemText(row, column=0)
            qFilePath, jobInfo = self.jobData.get(selected, ("", {}))
            jobDetails = self.detailedText(jobInfo)
            self.jobDetails.setText(jobDetails)

    def onDelete(self, sender, sel, ptr):
        """Dequeue any jobs no longer in the table"""
        deletedJobIds = {
            self.table.getItemText(row, column=0)
            for row in range(1, self.table.getNumRows())
            if self.table.isRowSelected(row)
        }
        self.jobDetails.setText("")
        for jobId, (qFilePath, jobInfo) in self.jobData.items():
            if jobId in deletedJobIds:
                # dequeue the deleted job
                self.queue.dequeue(qFilePath)

    def getHelp(self, sender, sel, ptr):
        "Open webbrowser to plugin helpUrl"
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
    kernelInitString="# QDir Queue Monitor {}".format(__version__),
    author=__author__,
    version=str(__version__),
    #applicableModules=["Job", "Visualization"],
    helpUrl=__url__,
    description="Check status of jobs in the QDir Queue",
)
