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

import sys
from pathlib import Path

from qdir import Queue, parser

parser.add_argument(
    "job", nargs="+", help="The list of job Ids or job names to dequeue."
)


def dequeueJobs(queue, jobList: list[str]):
    """Remove a list of jobIds or job names from the queue."""
    queuedJobs: dict[Path, dict] = {}
    queuedJobs.update(
        [
            (qFilePath, queue.getJobInfo(qFilePath))
            for qFilePath in queue.getQueuedJobs()
        ]
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


def qdel(argv):
    """Dequeue the specified jobId numbers or job names"""
    options = parser.parse_args(argv[1:])
    queue = Queue(**vars(options))
    dequeueJobs(queue, options.job)


def main():
    qdel(sys.argv)


if __name__ == "__main__":
    main()
