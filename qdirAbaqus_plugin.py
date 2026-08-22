"""Abaqus CAE plugin to interact with qdir Queue

Carl Osterwisch, August 2026
"""

from __future__ import print_function, with_statement

__version__ = '0.1.0'

import os
from abaqusGui import *

try:
    import qdir
except ImportError:
    qdir = None

class QueueTable(AFXTable):
    def deleteRows(self, startRow, numRows=1, notify=FALSE):
        """Delete rows and also notify the target"""
        AFXTable.deleteRows(self, startRow, numRows, notify)
        if notify:
            self.getTarget().handle(self, MKUINT(self.ID_DELETE_ROWS, SEL_UPDATE), None)

class QDirQueueMonitor(AFXDataDialog):
    (ID_TABLE, ID_REFRESH, ID_LAST) = range(AFXDataDialog.ID_LAST, AFXDataDialog.ID_LAST + 3)
    def __init__(self, form):
        AFXDataDialog.__init__(self, form,
                title="QDir Job Queue Monitor",
                actionButtonIds=self.DISMISS,
                opts=DIALOG_NORMAL|DECOR_RESIZE)
        self.queue = qdir.Queue()
        self.updateTimer = None
        self.headings = ('jobId', 'status', 'name')
        self.jobData = {}
        try:
            self.interval = 1000*max(1, int(os.environ.get("QDIR_POLL_INTERVAL", 5)))
        except ValueError:
            self.interval = 1000*5

        sp = FXSplitter(self, LAYOUT_FILL_X | LAYOUT_FILL_Y | SPLITTER_VERTICAL)
        self.table = QueueTable(
                p=sp,
                numVisRows=5,
                numVisColumns=len(self.headings),
                numRows=1,
                numColumns=len(self.headings),
                tgt=self,
                sel=self.ID_TABLE,
                opts=AFXTABLE_NORMAL|AFXTABLE_ROW_MODE)
        FXMAPFUNC(self, SEL_CLICKED, self.ID_TABLE, QDirQueueMonitor.onTableClicked)
        FXMAPFUNC(self, SEL_UPDATE, AFXTable.ID_DELETE_ROWS, QDirQueueMonitor.onDeleteRows)
        self.table.setLeadingRows(numRows=1)
        self.table.setLeadingRowLabels('\t'.join([h.title() for h in self.headings]))
        self.table.setColumnWidth(column=0, width=0)  # Hide the jobIds
        self.table.setColumnWidthInChars(column=1, numChars=30)
        self.table.setStretchableColumn(len(self.headings) - 1)  # Expand name as necessary
        self.table.setPopupOptions(AFXTable.POPUP_DELETE_ROW)
        self.history = FXText(p=sp, opts=TEXT_READONLY | LAYOUT_FILL_Y)
        self.history.setVisRows(5)
        if qdir is not None:
            FXMAPFUNC(self, SEL_TIMEOUT, self.ID_REFRESH, QDirQueueMonitor.updateTable)
        else:
            self.history.setText("qdir is not configured")

    def qstat(self):
        """Collect jobInfo of currently queued jobs"""
        queuedJobs = self.queue.getQueuedJobs()
        self.jobData.clear()
        for qFilePath in queuedJobs:
            jobInfo = qdir.getJobInfo(qFilePath)
            self.jobData[jobInfo['jobId']] = qFilePath, jobInfo

    def updateTable(self, *args):
        """Update manager with list of currently queued jobs"""
        row = self.table.getCurrentRow()
        if row < 1:
            selected = None  # nothing is selected
        else:
            selected = self.table.getItemText(row, column=0)
        self.qstat()
        diff = len(self.jobData) + 1 - self.table.getNumRows()
        if diff > 0:
            self.table.insertRows(
                    startRow=1,
                    numRows=diff,
                    notify=FALSE)
        elif diff < 0:
            self.table.deleteRows(
                    startRow=1,
                    numRows=-diff,
                    notify=FALSE)
        if len(self.jobData) > 0:
            history = ''
        else:
            h = []
            if "qdir" in session.queues:
                h.append("The job queue is empty.")
                h.append("You may Submit jobs to it by selecting qdir in the \"Run Mode\" for the Job.")
            else:
                h.append("Your qdir is not yet configured as a CAE job queue.")
            history = '\n'.join(h)

        for row, (qFilePath, jobInfo) in enumerate(self.jobData.values(), 1):
            for column, heading in enumerate(self.headings):
                self.table.setItemValue(
                        row=row,
                        column=column,
                        valueText=jobInfo.get(heading, ''),
                        )
            if jobInfo['jobId'] == selected:
                self.table.selectRow(row)
                history = '\n'.join(jobInfo.get('history', ''))
        self.history.setText(history)
        self.updateTimer = getAFXApp().addTimeout(self.interval, self, self.ID_REFRESH)

    def onTableClicked(self, sender, sel, ptr):
        """Show the job history data for selected job"""
        row = sender.getCurrentRow()
        if row > 0:
            selected = self.table.getItemText(row, column=0)
            qFilePath, jobInfo = self.jobData.get(selected, ('', {}))
            history = '\n'.join(jobInfo.get('history', []))
            self.history.setText(history)

    def onDeleteRows(self, sender, sel, ptr):
        """Dequeue any jobs no longer in the table"""
        activeJobIds = { self.table.getItemText(row, column=0)
                for row in range(1, self.table.getNumRows()) }
        for jobId, (qFilePath, jobInfo) in self.jobData.items():
            if jobId not in activeJobIds:
                # dequeue the deleted job
                qFilePath.unlink(missing_ok=True)

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

class QDirSetup(AFXDataDialog):
    """Simple guidance for common problems"""
    (ID_FILES, ID_DO_IT, ID_HELP, ID_LAST) = range(AFXDataDialog.ID_LAST, AFXDataDialog.ID_LAST + 4)
    def __init__(self, form):
        from textwrap import dedent
        AFXDataDialog.__init__(self, form,
                title="QDir Setup",
                opts=DIALOG_NORMAL|DECOR_RESIZE)
        dirname = os.path.dirname(os.path.normpath(__file__))
        required = "qdir", "qdir.py", "qdirAbaqus.py"
        if not all([os.path.exists(os.path.join(dirname, fn)) for fn in required]):
            AFXNote(self, "You have an incomplete installation in {}".format(dirname),
                    opts=NOTE_WARNING)
            FXLabel(self, "Please click [Files] to download the latest release.")
            self.appendActionButton("Files", self, self.ID_FILES)
        else:
            self.env = os.path.expanduser("~/abaqus_v6.env")
            AFXNote(self, "Abaqus CAE is not yet configured to use qdir.",
                    opts=NOTE_WARNING)
            t = AFXTextField(self, 20, "Add the following lines to the config file:",
                    opts=AFXTEXTFIELD_READONLY | LAYOUT_FILL_X)
            t.setText(self.env)
            f = FXHorizontalFrame(self, LAYOUT_FILL_X | FRAME_SUNKEN)
            self.info = FXText(p=f, opts=TEXT_READONLY | LAYOUT_FILL_X)
            self.info.setVisRows(7)
            config = dedent("""
                import sys
                sys.path.append(r"{path}")
                import qdirAbaqus
                qdirAbaqus.init(queues)
                run_mode = BATCH
                """).format(path=dirname)
            self.info.setText(config)
            self.appendActionButton("Do it for me", self, self.ID_DO_IT)
        self.appendActionButton("Help", self, self.ID_HELP)
        self.appendActionButton(self.DISMISS)

    def modifyConfig(self, sender, sel, ptr):
        """Append configuration to ~/abaqus_v6.env"""
        with open(self.env, 'wa') as envFile:
            print(self.info.getText(), file=envFile)

class QDirForm(AFXForm):
    def getFirstDialog(self):
        if qdir is None or 'qdir' not in session.queues:
            return QDirSetup(self)
        return QDirQueueMonitor(self)

###########################################################################
# Register the plugin
###########################################################################
toolset = getAFXApp().getAFXMainWindow().getPluginToolset()

toolset.registerGuiMenuButton(
    buttonText='&QDir Job Queue Monitor...',
    object=QDirForm(toolset),
    kernelInitString='# QDir Queue Monitor {}'.format(__version__),
    author='Carl Osterwisch',
    version=str(__version__),
    applicableModules=['Job'],
    description='Check status of jobs in the QDir Queue',
    )

