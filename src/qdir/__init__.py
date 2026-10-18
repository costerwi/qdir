#!/bin/env python3
"""Implementation of a first-in, first-out job queue for the local machine.

The queue is maintained as a directory of tiny job queue files.
When a new job is submitted, this script will identify any existing job queue files and then add its own queue file to the directory.
No job will begin until all the preceeding queue files are gone.
Each job will delete its own queue file upon completion so the next job can begin.
A shared queue directory should be specified on a multi-user system.
"""

__author__ = "Carl Osterwisch"
__version__ = "1.0.0rc2"
__url__ = "https://github.com/costerwi/qdir/"

import os
import signal
import subprocess
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from tempfile import gettempdir
from time import asctime, perf_counter, sleep

from filelock import FileLock

default = Namespace

parser = ArgumentParser(epilog=f"qdir {__version__} {__url__}")
default.queue = Path(os.environ.get("QDIR_QUEUE", gettempdir()))
parser.add_argument(
    "-q",
    "--queue",
    type=Path,
    help="Directory to store the queue files. "
    f"Default is environment variable QDIR_QUEUE or {default.queue}",
    default=default.queue,
)
default.verbose = int(os.environ.get("QDIR_VERBOSE", "2"))
parser.add_argument(
    "-v",
    "--verbose",
    type=int,
    help="Verbosity level. "
    f"Default is environment variable QDIR_VERBOSE or {default.verbose}",
    default=default.verbose,
)

qFileSuffix = os.environ.get("QDIR_SUFFIX", ".qdir")  # suffix for queue files


class Queue:
    def __init__(self, **kwargs):
        """Create the queue, allowing parameters to override defaults"""
        for parameter, value in vars(default).items():
            setattr(self, parameter, kwargs.pop(parameter, value))
        if not self.queue.is_dir():
            raise FileNotFoundError(f"The QDIR directory {self.queue} does not exist")
        if not os.access(self.queue, os.W_OK):
            raise PermissionError(f"The QDIR directory {self.queue} is not writable")

    def getQueuedJobs(self) -> list[Path]:
        """Return a list of qFilePath for currently queued jobs, sorted oldest to newest."""

        queuedJobs = [filePath for filePath in self.queue.glob("*" + qFileSuffix)]
        if len(queuedJobs) == 0:
            return queuedJobs  # easy answer

        # Collecct a set of active process ids
        if os.name == "nt":
            import win32process

            processIds = {str(pid) for pid in win32process.EnumProcesses()}
        else:
            procPath = Path("/proc")
            if procPath.is_dir():
                processIds = {p.stem for p in procPath.iterdir() if p.stem.isnumeric()}
            else:
                c = subprocess.run(
                    ["pgrep", "y"], stdout=subprocess.PIPE, text=True, check=True
                )
                processIds = {pid for pid in c.stdout.strip().split()}

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
                self.info.format(**self.getJobInfo(path)),
                file=sys.stderr,
            )
            try:
                path.unlink(missing_ok=True)
            except OSError as e:
                print(e, file=sys.stderr)

        # Filter valid qFiles
        queuedJobs = [filePath for filePath in queuedJobs if is_qFile(filePath)]
        return sorted(queuedJobs, key=lambda qFilePath: qFilePath.stat().st_mtime)

    def getJobInfo(self, qFilePath: Path) -> dict:
        """Return information about the job specified in qFilePath"""
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
        except OSError as e:
            status = repr(e)
            jobInfo["history"].append(status)
            jobInfo["status"] = status
        return jobInfo

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
            print(f"WARNING: {cmd[0]} is not in PATH", file=sys.stderr)
        if not self.interval > 0:
            self.interval = 1

        startTime = perf_counter()  # time job was enqueued
        job = None  # subprocess running the cmd, if any

        jobInfo = {  # information about this job
            "jobId": str(os.getpid()),  # process id of this script
            "owner": getpass.getuser(),
            "name": self.name or cmd[-1],
            "command": " ".join(cmd),
            "directory": Path.cwd(),
        }

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

        qFilePath = (self.queue / jobInfo["jobId"]).with_suffix(qFileSuffix)
        lock = FileLock(self.queue / "qdir.lock")  # prevent previousJobs race
        with lock.acquire(timeout=5):
            previousJobs = self.getQueuedJobs()
            jobInfo["behind"] = " ".join([job.stem for job in previousJobs])
            with qFilePath.open("w") as qFile:
                os.environ["QDIR_FILE"] = qFile.name  # will be exported to cmd
                # Initialize qFile contents
                for key in "name", "command", "directory", "behind":
                    value = jobInfo.get(key)
                    if value:
                        print(key, value, sep="\t", file=qFile)
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
            except OSError:
                pass  # ignore status update exceptions
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
                except OSError as e:
                    print(e, file=logFile)

        terminateJob()  # Clean up at the end


def humanDuration(seconds: float) -> str:
    for unit, per in ("days", 86400), ("hours", 3600), ("minutes", 60):
        if seconds >= 1.1 * per:
            return f"{seconds / per:.2g} {unit}"
    return f"{seconds:.2g} seconds"
