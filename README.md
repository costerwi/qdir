# qdir
A very low overhead first-in, first-out job queue for the local machine

The queue is maintained as a directory of tiny job status files.
When a new job is submitted, it will identify any existing status files and then add its own to the directory.
The job will not launch its command until all the preceeding status files are gone.
Each job will delete its own status file upon completion so the next job can begin.
There is a polling interval (default 5 seconds)
when the job checks to see if its predecessors have finished before launching its command.
A shared queue directory can be specified on a multi-user system to coordinate
job execution.
On Linux this is `/tmp` by default.

Any command may be submitted to the job queue using qsub
(see [usage](#usage) below).
There are also tools to check the status of the queue (qstat) and remove jobs (qdel).

# Installation
Requires python3 on Windows, Linux, or MacOS.
One way to get python3 on Windows is through the [Microsoft Store](https://apps.microsoft.com/detail/9PNRBTZXMB4Z).
Here is the command to install qdir once python3 is available:
```bash
python3 -m pip install qdir
```

See [here](https://pip.pypa.io/en/stable/installation/) if there is "no module named pip."

If there is a warning that the script directory is not in the PATH then
it must be added in order to use the command line tools.
Otherwise, [see below](#usage-without-script-directory-in-path).

## Abaqus Finite Element Analysis (FEA) extras
The package includes additional files to help Abaqus users submit and monitor the qdir job queue.
Use the following command to configure Abaqus after qdir itself has been installed:
```bash
python3 -m qdir.abaqus install
```

By default, the necessary settings are appended to the end of the user `abaqus_v6.env` file.
The following command may be used to remove qdir settings for Abaqus:
```bash
python3 -m qdir.abaqus uninstall
```

# Usage
Below is a brief overview of usage.
The command line tools accept a `-h` or `--help` argument to list their full options.

## Command line job submission
Submit commands or job scripts to the queue using the `qsub` command.
For example, on Linux:
```bash
qsub ./myJobFile.sh
```
or on Windows:
```bash
qsub myJobFile.cmd
```

Any printed output from the command will be saved to a file based on the job name with the job Id appended to the end.

Display command options with `qsub -h`

## Command line queue status
Check status with the `qstat` command, for example:
```bash
qstat
```

## Command line job removal
First use the `qstat` command above to find the job Ids and job names in the queue.
Delete or kill jobs with the `qdel` command followed by its jobId or job name.
For example, to delete job 12343:
```bash
qdel 12343
```

## Usage without script directory in PATH
The `qsub`, `qstat`, and `qdel` scripts are shortcuts to call python3 methods.
These scripts will not be available at the command line if their directory is not in the PATH.
It's most convenient to add the directory to the PATH but it is also
possible to run the methods directly with some additional typing,
such as `python3 -m qdir.qstat` to execute `qstat`

## Abaqus extras
Submit Abaqus jobs as usual from the command line:
```bash
abaqus job=whatever
```
Internally this will invoke the `qdir_submit.py` module to create a job script
and submit it to qdir.

You may submit jobs within Abaqus CAE by selecting `qdir` as the Job's queue before submitting.
You may check the queue status within CAE in the menu `Plug-ins > QDir Job Queue Monitor...`
Click on a Job to see more detailed information.
Right-click on a Job to expose the menu allowing you to delete the Job.

## Customization
Most parameters used by qdir may be customized with command line options,
system environment variables, or directives within the job script itself.

| Option | Description | Default |
|--------|-------------|---------|
| -N *NAME*, --name *NAME*  | Name for the job. | The last argument of the command |
| -q *QUEUE*, --queue *QUEUE* | Directory to store the queue files. | environment variable `QDIR_QUEUE` or `/tmp` on Linux |
| -c *INTERVAL*, --interval *INTERVAL* | Polling interval in seconds. | environment variable `QDIR_POLL_INTERVAL` or 5 |
| -i *INFO*, --info *INFO*  | Specify the format of information about jobs in queue | environment variable `QDIR_INFO` or `{jobId:8} {owner:12} {status:35} {name}` |
| -o *OUTPUT*, --output *OUTPUT* | File name for combined stdout and stderr. | environment variable `QDIR_LOGNAME` or `{name}._{jobId}`
| -s *STATUS*, --status *STATUS* | Specify the format of job status messages output to terminal. | environment variable `QDIR_STATUS` or `{jobId} {name} {status} after {duration}`
| -v *VERBOSE*, --verbose *VERBOSE* | Set the verbosity level. | environment variable `QDIR_VERBOSE` or 2 |
