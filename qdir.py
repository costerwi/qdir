#!/bin/env python3
"""Implementation of a first-in, first-out job queue for the local machine.

The queue is maintained as a directory of tiny job queue files.
When a new job is submitted, this script will identify any existing job queue files and then add its own queue file to the directory.
No job will begin until all the preceeding queue files are gone.
Each job will delete its own queue file upon completion so the next job can begin.
A shared queue directory should be specified on a multi-user system.

Carl Osterwisch, January 2024
"""

__version__ = "1.0.0"

from argparse import ArgumentParser, Namespace
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import gettempdir
from time import sleep, asctime, perf_counter

default = Namespace

parser = ArgumentParser(description=__doc__, epilog="Version " + __version__)
parser.add_argument(
    "-d",
    "--dequeue",
    action="store_true",
    help="Dequeue or terminate the job names or jobIds listed in args. "
    "Default behavior is to enqueue one job",
)
parser.add_argument(
    "-f",
    "--full",
    action="store_true",
    help="Report full detailed information about the job names or jobIds listed in args. "
    "All jobs are reported if none are specified.",
)
default.name = os.environ.get("PBS_JOBNAME")
parser.add_argument(
    "-N",
    "--name",
    help="Name for the job. Default is args[-1]",
    default=default.name,
)
default.queue = Path(os.environ.get("QDIR_QUEUE", gettempdir()))
parser.add_argument(
    "-q",
    "--queue",
    type=Path,
    help="Directory to store the queue files. "
    "Default is environment variable QDIR_QUEUE or {}".format(default.queue),
    default=default.queue,
)
try:
    default.interval = max(1, int(os.environ.get("QDIR_POLL_INTERVAL", 5)))
except ValueError:
    default.interval = 5
parser.add_argument(
    "-c",
    "--interval",
    type=int,
    help="Polling interval in seconds. "
    "Default is environment variable QDIR_POLL_INTERVAL or {}".format(default.interval),
    default=default.interval,
)
default.info = os.environ.get("QDIR_INFO", "{jobId:8} {owner:12} {status:35} {name}")
parser.add_argument(
    "-i",
    "--info",
    help="Specify the format of information about jobs in queue. "
    "Default is environment variable QDIR_INFO or {!r}".format(default.info),
    default=default.info,
)
default.output = os.environ.get("QDIR_LOGNAME", "{name}._{jobId}")
parser.add_argument(
    "-o",
    "--output",
    help="File name for combined stdout and stderr. "
    "Default is environment variable QDIR_LOGNAME or {!r}".format(default.output),
    default=default.output,
)
default.status = os.environ.get(
    "QDIR_STATUS", "{jobId} {name} {status} after {duration}"
)
parser.add_argument(
    "-s",
    "--status",
    help="Specify the format of job status messages output to terminal. "
    "Default is environment variable QDIR_STATUS or {!r}".format(default.status),
    default=default.status,
)
default.verbose = int(os.environ.get("QDIR_VERBOSE", 2))
parser.add_argument(
    "-v",
    "--verbose",
    type=int,
    help="Verbosity level. "
    "Default is environment variable QDIR_VERBOSE or {}".format(default.verbose),
    default=default.verbose,
)
parser.add_argument(
    "args",
    nargs="*",
    help="The command to enqueue and any optional arguments. "
    "This command must be in your PATH or explicitly specified. "
    "If no command is given then the currently queued jobs are listed.",
)

qFileSuffix = os.environ.get("QDIR_SUFFIX", ".qdir")  # suffix for queue files
dprefix = os.environ.get(
    "QDIR_DPREFIX",
    os.environ.get("PBS_DPREFIX", "(#|@?(?i:rem ))(QDIR|PBS)"),
)  # regular expression prefix used to recognize optional file directives

if os.name == "nt":
    def winOwner(self) -> str:
        "Return name of the WindowsPath owner"
        try:
            import win32security
        except ImportError:
            if options.verbose >= 3:
                print(
                    "Unable to determine owner without win32security module",
                    file=sys.stderr,
                )
            return "unknown"
        sd = win32security.GetFileSecurity(
            str(self), win32security.OWNER_SECURITY_INFORMATION
        )
        owner_sid = sd.GetSecurityDescriptorOwner()
        name, domain, type = win32security.LookupAccountSid(None, owner_sid)
        return name

    try:
        _ = Path(".").owner()  # test if Path has owner method
    except NotImplementedError:
        Path.owner = winOwner  # monkey patch if needed

class Queue:
    def __init__(self, **kwargs):
        """Create the queue, allowing parameters to override defaults"""
        for parameter, value in vars(default).items():
            setattr(self, parameter, kwargs.pop(parameter, value))
        if not self.queue.is_dir():
            raise FileNotFoundError(f"The QDIR directory {self.queue} does not exist")
        if not os.access(self.queue, os.W_OK):
            raise PermissionError(f"The QDIR directory {self.queue} is not writable")
        if not self.interval > 0:
            raise ValueError(
                f"The QDIR_POLL_INTERVAL {options.interval} must be seconds greater than 0"
            )

    def getQueuedJobs(self) -> list[Path]:
        """Return a list of qFilePath for currently queued jobs, sorted oldest to newest."""
        # Collecct a set of active process ids
        if os.name == "nt":
            import win32process
            processIds = {str(pid) for pid in win32process.EnumProcesses()}
        else:
            procPath = Path("/proc")
            processIds = {p.stem for p in procPath.iterdir() if p.stem.isnumeric()}

        def is_qFile(path):
            """Verify the path is an active job file with a matching process id"""
            if not path.stem.isnumeric():
                return False  # file name must be an integer
            if not (path.is_file()):
                return False  # path must represent a file
            if path.stem in processIds:
                return True  # file name must match a running process number

            # Otherwise, the process may have died or the computer was rebooted with
            # this job in the queue. This orphaned qFile may be removed.
            print(
                "Removing orphaned queue file",
                self.info.format(**getJobInfo(path)),
                file=sys.stderr,
            )
            try:
                path.unlink(missing_ok=True)
            except OSError as e:
                print(e, file=sys.stderr)

        queuedJobs = [
            filePath
            for filePath in self.queue.glob("*" + qFileSuffix)
            if is_qFile(filePath)
        ]
        return sorted(queuedJobs, key=lambda qFilePath: qFilePath.stat().st_mtime)

    def dequeue(self, qFilePath: Path):
        """Remove a job from the queue"""
        assert qFilePath.parent == self.queue
        assert qFilePath.suffix == qFileSuffix
        assert qFilePath.stem.isnumeric()
        # Removing qFile will dequeue the job but the effect is delayed by polling interval
        qFilePath.unlink(missing_ok=True)
        if os.name == "posix":
            # On Linux the SIGTERM signal has immediate effect
            try:
                os.kill(int(qFilePath.stem), signal.SIGTERM)
            except OSError:  # no such process
                pass

    def enqueue(self, cmd: list[str]):
        """Wait in queue until prior jobs finish, then run cmd"""
        import getpass
        import shutil

        if len(cmd) < 1:
            raise SyntaxError("Missing cmd")
        if self.verbose >= 1 and not shutil.which(cmd[0]):
            print("WARNING: {} is not in PATH".format(cmd[0]), file=sys.stderr)

        if os.name == "posix":
            # fork to background
            if os.fork():
                os._exit(0)

        previousJobs = self.getQueuedJobs()
        jobInfo = {  # information about this job
            "jobId": str(os.getpid()),  # process id of this script
            "owner": getpass.getuser(),
            "name": self.name or cmd[-1],
            "command": " ".join(cmd),
            "directory": Path.cwd(),
            "behind": " ".join([job.stem for job in previousJobs]),
            "status": "",
        }
        job = None  # subprocess running the cmd, if any

        def updateStatus(priority, status, file=None):
            """Notify user of status change and optionally record in file"""
            jobInfo["status"] = status
            jobInfo["time"] = asctime()
            jobInfo["duration"] = humanDuration(perf_counter() - startTime)
            if self.verbose >= priority:
                # Echo status to the terminal
                print(self.status.format(**jobInfo))
            if file is not None:
                # Record status history in specified qFile
                print("{time} {status}".format(**jobInfo), file=file)

        # Create the qFile in qdir directory based on this jobId
        qFilePath = (self.queue / jobInfo["jobId"]).with_suffix(qFileSuffix)
        with qFilePath.open("w") as qFile:
            os.environ["QDIR_FILE"] = qFile.name  # will be exported to cmd
            # Initialize qFile contents for qstat information
            for key in "name", "command", "directory", "behind":
                value = jobInfo.get(key)
                if value:
                    print(key, value, sep="\t", file=qFile)
            startTime = perf_counter()  # time job was enqueued
            updateStatus(priority=2, status="Queued", file=qFile)

        def terminateJob(sig=None, frame=None):
            """Terminate this job if running or dequeue if not"""
            nonlocal job
            result = ""
            qFilePath.unlink(missing_ok=True)  # remove its qFile
            if job is None:
                # removed from the queue before starting
                result = ".. Dequeued"
            elif hasattr(job, "pid"):  # job is or was running
                if job.poll() is None:
                    # job is still running
                    if self.verbose >= 2:
                        result = ".. Killed"
                    if os.name == "nt":
                        job.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        # pass SIGTERM signal to all child processes in this process group
                        os.killpg(os.getpgid(job.pid), signal.SIGTERM)
                elif self.verbose >= 1:
                    # job is no longer running; check returncode
                    if job.returncode <= 0:
                        result = "** Done"
                    else:
                        result = "-- Error"
            if result:
                updateStatus(priority=2, status=result)
                job = result  # prevent this from duplicate reporting

        signal.signal(
            signal.SIGTERM, terminateJob
        )  # catch termination signal (ignored on Windows)

        # Wait for all previousJobs to complete
        previousJobs.reverse()  # check newest jobs first
        while qFilePath.exists() and any(
            otherFile.exists() for otherFile in previousJobs
        ):
            sleep(self.interval)

        # Launch the cmd only if this job's qFile still exists
        if qFilePath.exists():
            try:
                # Append the job starting status to qFile
                stat = qFilePath.stat()
                with qFilePath.open("a") as qFile:
                    print(
                        "Waited in queue",
                        humanDuration(perf_counter() - startTime),
                        file=qFile,
                    )
                    updateStatus(priority=3, status="Started", file=qFile)
                # Keep mtime unchanged so the job files sort correctly
                os.utime(qFilePath, (stat.st_atime, stat.st_mtime))
            except Exception:
                pass  # ignore any status update exceptions
            logFilePath = Path(self.output.format(**jobInfo))
            with logFilePath.open("w") as logFile:
                opts = {}
                if os.name == "nt":
                    opts["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
                try:
                    job = subprocess.Popen(
                        cmd,
                        shell=False,
                        start_new_session=True,
                        stdin=subprocess.DEVNULL,
                        stdout=logFile,
                        stderr=subprocess.STDOUT,
                        **opts,
                    )
                    startTime = perf_counter()  # reset to time job started running
                    while qFilePath.exists() and job.poll() is None:
                        # job is still running
                        sleep(self.interval)
                except Exception as e:
                    print(e, file=logFile)

        terminateJob()  # Clean up at the end

def getJobInfo(qFilePath: Path) -> dict:
    """Return information about the job specified in qFilePath"""
    assert qFilePath.suffix == qFileSuffix
    assert qFilePath.stem.isnumeric()
    jobInfo = {
        "jobId": qFilePath.stem,
        "owner": qFilePath.owner(),
        "name": "",
        "command": "",
        "directory": "",
        "behind": "",
        "status": "",
        "history": [],  # list[str]
    }
    try:
        with qFilePath.open() as qFile:
            for line in qFile:
                keyValue = line.strip().split("\t", 2)
                if len(keyValue) == 2:
                    jobInfo.update([keyValue])
                else:
                    status = keyValue[0]
                    jobInfo["history"].append(status)
                    jobInfo["status"] = status  # latest update
    except Exception as e:
        status = repr(e)
        jobInfo["history"].append(status)
        jobInfo["status"] = status
    return jobInfo

def parseArguments(argv: list[str]) -> Namespace:
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

    # Scan args[0] for optional file directives
    directives = []
    dprefixRe = re.compile(dprefix)
    commentRe = re.compile("(#|@?(?i:rem|echo))")
    try:
        with open(argvNamespace.args[0]) as jobScript:
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
    except:
        pass
    _, unknown = parser.parse_known_args(directives)

    # Finally, parse the combined options with priority for argv
    options, _ = parser.parse_known_args(directives + argv)

    # Always overwrite these options which must come from argv
    argvOnly = "args", "dequeue", "full"
    vars(options).update({k: vars(argvNamespace).get(k) for k in argvOnly})

    if not options.name and len(options.args) > 0:
        options.name = options.args[0]  # default name
    if unknown and options.verbose >= 2:
        print("WARNING: Unknown file directives", *unknown, file=sys.stderr)
    if options.verbose >= 5:
        print("Arguments", argv, file=sys.stderr)
        print("Directives", directives, file=sys.stderr)
        print("options", options, file=sys.stderr)
    return options

def printStatus(queue, jobList: list[str]):
    """Print a list of queued jobs"""
    if queue.verbose >= 2:
        print("Queue directory", queue.queue)
    queuedJobs = queue.getQueuedJobs()
    if not queuedJobs and queue.verbose >= 2:
        print("No jobs queued")
    jobHeadings = None
    for qFilePath in queuedJobs:
        jobInfo = getJobInfo(qFilePath)
        if not jobHeadings and queue.verbose >= 1:
            jobHeadings = {k: k.upper() for k in jobInfo}
            print(queue.info.format(**jobHeadings))
        if len(jobList) == 0 or jobInfo["jobId"] in jobList or jobInfo["name"] in jobList:
            print(queue.info.format(**jobInfo))

def printDetails(queue, jobList: list[str]):
    """Report full details about queued jobs"""
    if queue.verbose >= 2:
        print("Queue directory", queue.queue)
    queuedJobs = queue.getQueuedJobs()
    if not queuedJobs and queue.verbose >= 2:
        print("No jobs queued")

    for qFilePath in queuedJobs:
        jobInfo = getJobInfo(qFilePath)
        if len(jobList) == 0 or jobInfo["jobId"] in jobList or jobInfo["name"] in jobList:
            print("")
            for key, value in jobInfo.items():
                if "status" == key:
                    continue  # Will be included with full history
                if isinstance(value, list):
                    print(key.upper(), *value, sep="\n")
                elif value:
                    print("{:10} {}".format(key.upper(), value))

def dequeueJobs(queue, jobList: list[str]):
    """Remove a list of jobIds or job names from the queue."""
    if not jobList:
        raise ValueError("ERROR: No jobs specified to dequeue")
    queuedJobs: dict[Path, dict] = {}
    queuedJobs.update(
        [(qFilePath, getJobInfo(qFilePath)) for qFilePath in queue.getQueuedJobs()]
    )
    if not queuedJobs and queue.verbose >= 2:
        print("No jobs queued", file=sys.stderr)
    for job in jobList:
        matched = 0
        for qFilePath, jobInfo in queuedJobs.items():
            if job == jobInfo.get("jobId") or job == jobInfo.get("name"):
                # Matched either jobId or job name
                matched += 1
                if queue.verbose >= 3:
                    print("Dequeing", queue.info.format(**jobInfo))
                queue.dequeue(qFilePath)
        if matched == 0 and queue.verbose >= 1:
            print(job, "is not queued", file=sys.stderr)

def humanDuration(seconds: float) -> str:
    for unit, per in ("days", 86400), ("hours", 3600), ("minutes", 60):
        if seconds >= 1.1 * per:
            return "{:.2g} {}".format(seconds / per, unit)
    return "{:.2g} seconds".format(seconds)

def qsub():
    """Enqueue a new command"""
    options = parseArguments(sys.argv[1:])
    queue = Queue(**vars(options))
    queue.enqueue(options.args)

def qstat():
    """Report status of the queue"""
    options = parseArguments(sys.argv[1:])
    queue = Queue(**vars(options))
    if options.full:
        # Report detailed information about jobs in the queue
        printDetails(queue, options.args)
    else:
        # Report list of jobs in queue
        printStatus(queue, options.args)

def qdel():
    """Dequeue the specified jobId numbers or job names"""
    options = parseArguments(sys.argv[1:])
    queue = Queue(**vars(options))
    dequeueJobs(queue, options.args)

if __name__ == "__main__":
    alias = Path(sys.argv[0]).stem
    if alias == "qstat":
        qstat()
    elif alias == "qdel":
        qdel()
    elif len(sys.argv) > 1:
        # default behavior is to add a job into the queue
        qsub()

