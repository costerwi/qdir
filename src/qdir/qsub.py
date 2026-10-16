#!/bin/env python3
"""Implementation of a first-in, first-out job queue for the local machine.

The queue is maintained as a directory of tiny job queue files.
When a new job is submitted, this script will identify any existing job queue files and then add its own queue file to the directory.
No job will begin until all the preceeding queue files are gone.
Each job will delete its own queue file upon completion so the next job can begin.
A shared queue directory should be specified on a multi-user system.

Carl Osterwisch, January 2024
Latest version: https://github.com/costerwi/qdir/
"""

import os
import subprocess
import sys

from qdir import Queue, default, parser

dprefix = os.environ.get(
    "QDIR_DPREFIX",
    os.environ.get("PBS_DPREFIX", "(#|@?(?i:rem ))(QDIR|PBS)"),
)  # regular expression prefix used to recognize optional file directives

default.name = os.environ.get("PBS_JOBNAME")
parser.add_argument(
    "-N",
    "--name",
    help="Name for the job. Default is cmd[-1]",
    default=default.name,
)
try:
    default.interval = max(1, int(os.environ.get("QDIR_POLL_INTERVAL", "5")))
except ValueError:
    default.interval = 5
parser.add_argument(
    "-c",
    "--interval",
    type=int,
    help="Polling interval in seconds. "
    f"Default is environment variable QDIR_POLL_INTERVAL or {default.interval}",
    default=default.interval,
)
parser.add_argument(
    "-f",
    "--foreground",
    action="store_true",
    help="Prevent qsub from forking to wait in background.",
    default=False,
)
default.output = os.environ.get("QDIR_LOGNAME", "{name}._{jobId}")
parser.add_argument(
    "-o",
    "--output",
    help="File name for combined stdout and stderr. "
    f"Default is environment variable QDIR_LOGNAME or {default.output!r}",
    default=default.output,
)
default.status = os.environ.get(
    "QDIR_STATUS", "{jobId} {name} {status} after {duration}"
)
parser.add_argument(
    "-s",
    "--status",
    help="Specify the format of job status messages output to terminal. "
    f"Default is environment variable QDIR_STATUS or {default.status!r}",
    default=default.status,
)
parser.add_argument(
    "cmd",
    nargs="+",
    help="The command to enqueue and any optional arguments. "
    "This command must be in your PATH or explicitly specified. ",
)


def parseArguments(argv: list[str]):
    """Parse the given list of arguments

    Uses commandline arguments for top priority followed by in-file directives
    and lastly default values.

    In-file directives are the same format as commandline options and should
    occur in comment lines at the beginning of the job script.
    Directive lines and are preceeded by the dprefix regular expression.
    """

    import re
    import shlex

    # Parse commandline arguments to find cmd
    argvNamespace = parser.parse_args(argv)

    # Scan cmd[0] for optional file directives
    directives = []
    dprefixRe = re.compile(dprefix)
    commentRe = re.compile("(#|@?(?i:rem|echo))")
    try:
        with open(argvNamespace.cmd[0]) as jobScript:
            for line in jobScript:
                m = dprefixRe.match(line)
                if m:
                    directives.extend(shlex.split(line[m.end() :]))
                elif len(line.strip()) == 0:
                    continue  # ignore blank lines
                elif commentRe.match(line):
                    continue  # ignore non-directive comment lines
                else:
                    break  # otherwise stop processing
    except OSError:
        pass
    directives.append("cmd")
    _, unknown = parser.parse_known_args(directives)

    # Finally, parse the combined options with priority for argv
    options, _ = parser.parse_known_args(directives + argv)

    # The cmd may only come from argv
    options.cmd = argvNamespace.cmd

    if not options.name and len(options.cmd) > 0:
        options.name = options.cmd[-1]  # default name
    if unknown and options.verbose >= 2:
        print("WARNING: Unknown file directives", *unknown, file=sys.stderr)
    if options.verbose >= 5:
        print("Arguments", argv, file=sys.stderr)
        print("Directives", directives, file=sys.stderr)
        print("options", options, file=sys.stderr)
    return options


def qsub(argv):
    """Enqueue a new command"""
    options = parseArguments(argv[1:])
    if not options.foreground:
        cmd = [sys.executable, "-m", "qdir.qsub", "-f"] + argv[1:]
        subprocess.Popen(cmd, start_new_session=True)  # re-run in background
    else:
        queue = Queue(**vars(options))
        queue.enqueue(options.cmd)


def main():
    qsub(sys.argv)


if __name__ == "__main__":
    main()
