"""Abaqus Queue class to create a job script and submit it to qdir

This file may be included by adding the following to custom_v6.env:

import sys
sys.path.append(r"C:/path/to/here")  # specify directory of this file
from qdirQueue import QDirQueue
queues['default'] = QDirQueue()
run_mode = BATCH
del sys

Carl Osterwisch, January 2024
"""

from __future__ import print_function, with_statement
from driverQueues import Queue


class QDirQueue(Queue):
    """Submits jobs to a qdir queue."""

    def __init__(self):
        import os
        from textwrap import dedent
        from string import Template

        if hasattr(Queue, '__init__'):
            Queue.__init__(self)
        if os.name == "posix":
            self.extension = ".sh"
            self.template = Template(
                dedent(
                    """\
                #!/bin/sh
                #QDIR --name $job
                #QDIR --output {name}.log
                JOB="$job"
                ABAQUS=$abaqus
                $exports
                cd $$(dirname $$0)

                let t=0
                while [[ -e "$$JOB.lck" && $$t != 90 ]]
                do
                    let t+=5
                    echo Paused $$t seconds for \"$$JOB.lck\" to clear
                    sleep 5
                done

                umask 0007
                exec $$ABAQUS python -u "$$JOB.com"
                """
                )
            )
        else:
            self.extension = ".cmd"
            self.template = Template(
                dedent(
                    """\
                @echo off
                rem QDIR --name $job
                rem QDIR --output {name}.log
                set JOB=$job
                set ABAQUS=$abaqus
                $exports
                cd /D %~dp0

                set t=0
                :do
                if not exist %JOB%.lck goto done
                    set /a t+=5
                    echo Paused %t% seconds for \"%JOB%.lck\" to clear
                    ping 127.0.0.1 -n 5 >nul
                    if not %t%==90 goto do
                :done

                %ABAQUS% python -u %JOB%.com
                """
                )
            )

    def exports(self, options, env):
        "Override to return a string which will be inserted into the command script"
        pass

    def createJobScript(self, options, env):
        "Create script to run Abaqus job"

        import os

        job = options["job"]
        scriptName = os.path.join(".", job + self.extension)
        with open(scriptName, "w") as jobFile:
            print(
                self.template.substitute(
                    abaqus=env["ABA_COMMAND"],
                    job=job,
                    exports=self.exports(options, env) or "",
                ),
                file=jobFile,
            )
        try:
            os.chmod(scriptName, 0o775)  # Set permissions
        except OSError:
            pass
        return scriptName

    def submit(self, options, env):
        "Create Abaqus job script and submit it to qdir"

        cmd = 'qdir "{}"'.format(self.createJobScript(options, env))
        localenv = env.copy()
        if "PYTHONPATH" in localenv:
            del localenv["PYTHONPATH"]  # avoid version conflicts
        return self.spawn(cmd, localenv, options.get("verbose", 0))
