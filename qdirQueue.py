"""Abaqus Queue class to create a job script and submit it to qdir

This module is compatible with at least Abaqus 2019 thru 2026.
This module works under Windows and Linux.

Installation:

Add the following lines to your Abaqus custom_v6.env file:

import sys
sys.path.append(r"C:/path/to/here/")  # specify directory of qdirQueue.py
import qdirQueue
qdirQueue.init(queues)
run_mode = BATCH

Usage:

Abaqus jobs from the command line will submit to the queue by default.

abaqus job=whatever

Abaqus CAE may submit to the queue by selecting it in the Job dialog.


Carl Osterwisch, January 2024
"""

from __future__ import print_function, with_statement  # use Python3 syntax

__all__ = ["QDirQueue"]

import os
from string import Template
from textwrap import dedent

from driverQueues import Queue
import uti


def init(queues, queue=None):
    """Add the queue instance, QDirQueue() by default, to dict of solver queues"""
    if queue is None:
        queue = QDirQueue()
    qName = getattr(queue, 'name', 'qdir')
    queues[qName] = queue
    queues.setdefault('default', queue)
    initCAE(qName)  # also add to CAE
    return qName


def initCAE(qName):
    """Add queue name to list of selectable Abaqus CAE Job queues"""
    try:
        from abaqus import session, addImportCallback
        print('Adding {} to CAE Job queue options'.format(qName))
        def addQueue(*args):
            session.Queue(name=qName, queueName=qName)
        addImportCallback('job', addQueue)
    except ImportError:
        pass  # not running within CAE


class QDirQueue(Queue):
    """Creates a job script and submits it to a qdir queue."""
    def __init__(self):
        if hasattr(Queue, "__init__"):
            Queue.__init__(self)
        self.name = "qdir"
        if uti.getPlatform().startswith("win"):
            # Windows OS
            self.extension = ".cmd"  # job script filename extension
            self.setenv = "set"  # command to set environment variables
            self.template = Template(  # job script template
                dedent(
                    """\
                @echo off
                rem QDIR --name "$job"
                rem QDIR --output "{name}.log"
                set JOB="$job"
                set ABAQUS="$abaqus"
                $exports
                cd /D "%~dp0"

                set t=0
                :do
                if not exist %JOB%.lck goto done
                    set /a t+=5
                    echo Paused %t% seconds for %JOB%.lck to clear
                    ping 127.0.0.1 -n 6 >nul
                    if not %t%==90 goto do
                :done

                %ABAQUS% python -u %JOB%.com
                """
                )
            )

        else:
            # Non-Windows OS
            self.extension = ".sh"  # job script filename extension
            self.setenv = "export"  # command to set environment variables
            self.template = Template(  # job script template
                dedent(
                    """\
                #!/bin/sh
                #QDIR --name "$job"
                #QDIR --output "{name}.log"
                JOB="$job"
                ABAQUS="$abaqus"
                $exports
                cd "$$(dirname "$$0")"

                let t=0
                while [[ -e "$$JOB.lck" && $$t != 90 ]]
                do
                    let t+=5
                    echo Paused $$t seconds for $$JOB.lck to clear
                    sleep 5
                done

                umask 0007
                exec "$$ABAQUS" python -u "$$JOB.com"
                """
                )
            )

    def exports(self, options, env):
        """Return a dict of os.environ settings to be inserted into the command script"""
        extraEnviron = {}
        if uti.getProductVersion() == "Abaqus 2026":
            extraEnviron["ABQ_DLALLOCATOR"] = "1"  # example usage for BR10000415659
        return extraEnviron

    def createJobScript(self, options, env):
        """Create script to run Abaqus job"""
        job = options["job"]
        scriptName = os.path.join(".", job + self.extension)
        exports = self.exports(options, env) or ""
        if isinstance(exports, dict):
            # expand dict of os.environ settings to multiline str
            exports = "\n".join(
                self.setenv + " {0}={1}".format(*i) for i in sorted(exports.items())
            )

        with open(scriptName, "w") as jobFile:
            print(
                self.template.substitute(
                    abaqus=env["ABA_COMMAND"],
                    job=job,
                    exports=exports,
                ),
                file=jobFile,
            )
        try:
            os.chmod(scriptName, 0o775)  # Set permissions
        except OSError:
            pass
        return scriptName

    def submit(self, options, env):
        """Create Abaqus job script and submit it to qdir"""
        dirname = os.path.dirname(__file__)
        qdir = os.path.join(dirname, 'qdir')  # full path to qdir
        scriptName = self.createJobScript(options, env)
        cmd = '{} {!r}'.format(qdir, scriptName)
        localenv = env.copy()
        if "PYTHONPATH" in localenv:
            del localenv["PYTHONPATH"]  # avoid version conflicts
        return self.spawn(cmd, localenv, options.get("verbose", 0))

