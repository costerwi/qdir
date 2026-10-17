"""Abaqus Queue class to create a job script and submit it to qdir

This module is compatible with at least Abaqus 2019 thru 2026.
This module works under Windows and Linux.

Carl Osterwisch, January 2024
"""

from __future__ import print_function, with_statement  # use Python3 syntax

__all__ = ["QDirQueue"]

import os
from string import Template
from textwrap import dedent

import uti
from driverQueues import Queue

dirname = os.path.dirname(os.path.normpath(__file__))


def init(queues, queue=None):
    """Add the queue instance, QDirQueue() by default, to dict of solver queues"""
    if queue is None:
        queue = QDirQueue()
    qName = getattr(queue, "name", "qdir")
    queues[qName] = queue  # add to solver
    queues.setdefault("default", queue)
    initCAE(qName)  # also add to CAE
    return qName


def initCAE(qName):
    """Register callback to add qName to Abaqus CAE Job queues"""
    try:
        from abaqus import addImportCallback, session
    except ImportError:
        return  # not running within CAE

    def addQueue(*args):
        """Add qName to list of selectable Abaqus CAE Job queues"""
        if qName not in session.queues:
            session.Queue(name=qName, queueName=qName)

    addImportCallback("job", addQueue)


def submitCAEJobs(jobList=None, qName="qdir"):
    """For specified CAE Jobs (all by default), set the queue and submit to queue"""
    from abaqus import mdb

    for job in mdb.jobs.values():
        if not jobList or job.name in jobList:
            print("Submitting {} to {}".format(job.name, qName))
            job.setValues(queue=qName)
            job.submit()


class QDirQueue(Queue):
    """Creates a job script and submits it to a qdir queue."""

    def __init__(self):
        if hasattr(Queue, "__init__"):
            Queue.__init__(self)
        self.name = "qdir"
        if uti.getPlatform().startswith("win"):
            # Windows OS
            self.extension = ".cmd"  # job script filename extension
            self.setenv = "set"  # shell command to set environment variables
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
            self.setenv = "export"  # shell command to set environment variables
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
        """Create shell script to run Abaqus job"""
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
        scriptName = self.createJobScript(options, env)
        cmd = "qsub {!r}".format(scriptName)
        localenv = env.copy()
        if "PYTHONPATH" in localenv:
            del localenv["PYTHONPATH"]  # avoid version conflicts
        return self.spawn(cmd, localenv, options.get("verbose", 0))
