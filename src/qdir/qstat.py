#!/bin/env python3
"""Report currrent status of the qdir job queue"""

import json
import os
import sys
from pathlib import Path

from qdir import Queue, default, parser

parser.description = __doc__
parser.add_argument(
    "-f",
    "--full",
    action="store_true",
    help="Report full detailed information in text format.",
)
parser.add_argument(
    "-j",
    "--json",
    action="store_true",
    help="Report full detailed queue status in json format.",
)
default.info = os.environ.get("QDIR_INFO", "{jobId:8} {owner:12} {status:35} {name}")
parser.add_argument(
    "-i",
    "--info",
    help="Specify the shortened format of job information "
    "when neither --full nor --json are specified. "
    f"Default is environment variable QDIR_INFO or {default.info!r}",
    default=default.info,
)
parser.add_argument(
    "job",
    nargs="*",
    help="An optional list of job Ids or job names to get status. "
    "If no jobs are specified then all currently queued jobs will be listed.",
)


if os.name == "nt":

    def winOwner(self) -> str:
        "Return name of the WindowsPath owner"
        try:
            import win32security
        except ImportError:
            return "unknown"
        sd = win32security.GetFileSecurity(
            str(self), win32security.OWNER_SECURITY_INFORMATION
        )
        owner_sid = sd.GetSecurityDescriptorOwner()
        name, _domain, _type = win32security.LookupAccountSid(None, owner_sid)
        return name

    try:
        _ = Path(".").owner()  # test if Path has owner method
    except NotImplementedError:
        Path.owner = winOwner  # monkey patch if needed


def printStatus(queue, jobList: list[str]):
    """Print a list of queued jobs"""
    if queue.verbose >= 2:
        print("Queue directory", queue.queue)
    queuedJobs = queue.getQueuedJobs()
    if not queuedJobs and queue.verbose >= 2:
        print("No jobs queued")
    jobHeadings = None
    for qFilePath in queuedJobs:
        jobInfo = queue.getJobInfo(qFilePath)
        if (
            len(jobList) == 0
            or jobInfo["jobId"] in jobList
            or jobInfo["name"] in jobList
        ):
            if not jobHeadings and queue.verbose >= 1:
                jobHeadings = {k: k.upper() for k in jobInfo}
                print(queue.info.format(**jobHeadings))
            print(queue.info.format(**jobInfo))


def printDetails(queue, jobList: list[str]):
    """Report full details about queued jobs"""
    if queue.verbose >= 2:
        print("Queue directory", queue.queue)
    queuedJobs = queue.getQueuedJobs()
    if not queuedJobs and queue.verbose >= 2:
        print("No jobs queued")

    for position, qFilePath in enumerate(queuedJobs, 1):
        jobInfo = queue.getJobInfo(qFilePath)
        jobInfo["position"] = position
        if (
            len(jobList) == 0
            or jobInfo["jobId"] in jobList
            or jobInfo["name"] in jobList
        ):
            print()
            for key, value in jobInfo.items():
                if "status" == key:
                    continue  # Will be included with full history
                if isinstance(value, list):
                    print(key.upper(), *value, sep="\n")
                elif value:
                    print(f"{key.upper():10} {value}")


def printJSON(queue, jobList: list[str]):
    """Output detailed queue status in JSON format"""
    jobs = []
    for position, qFilePath in enumerate(queue.getQueuedJobs(), 1):
        jobInfo = queue.getJobInfo(qFilePath)
        jobInfo["position"] = position
        if (
            len(jobList) == 0
            or jobInfo["jobId"] in jobList
            or jobInfo["name"] in jobList
        ):
            jobs.append(jobInfo)
    print(json.dumps(jobs, indent=2))


def qstat(argv):
    """Report status of the queue"""
    options = parser.parse_args(argv[1:])
    queue = Queue(**vars(options))
    if options.full:
        # Report detailed information about jobs in the queue
        printDetails(queue, options.job)
    elif options.json:
        # Report detailed queue status in json format
        printJSON(queue, options.job)
    else:
        # Report list of jobs in queue
        printStatus(queue, options.job)


def main():
    qstat(sys.argv)


if __name__ == "__main__":
    main()
