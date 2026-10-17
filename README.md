# qdir
A very low overhead first-in, first-out job queue for the local machine

The queue is maintained as a directory of tiny job queue files.
When a new job is submitted, this script will identify any existing job queue files and then add its own queue file to the directory.
No job will begin until all the preceeding queue files are gone.
Each job will delete its own queue file upon completion so the next job can begin.
A shared queue directory can be specified on a multi-user system.
On Linux this is `/tmp` by default.

Any command may be submitted to the job queue using qsub (see usage below).
You may check the status of the queue (qstat) and remove jobs (qdel).

# Installation
Requires python3 running on Windows or Linux.
One way to get python3 on Windows is through the [Microsoft Store](https://apps.microsoft.com/detail/9PNRBTZXMB4Z).
Here is the command to install qdir once you have python3 available:
```bash
python3 -m pip install qdir
```

See [here](https://pip.pypa.io/en/stable/installation/) if there is "no module named pip."

## Abaqus Finite Element Analysis (FEA) extras
The package includes additional files to help Abaqus users submit and monitor the qdir job queue.
Use the following command to configure Abaqus after qdir itself has been installed:
```bash
python3 -m qdir.abaqus install
```

By default, the necessary settings are appended to the end of your user `abaqus_v6.env` file.
To uninstall you may removed the settings manually or with this command:
```bash
python3 -m qdir.abaqus uninstall
```

# Usage

## Command line job submission
Submit commands or scripts to the queue using the `qsub` command.
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
or, for full details:
```bash
qstat -f
```

## Command line job removal
First use the `qstat` command above to find the jobIds and job names in the queue.
Delete or kill jobs with the `qdel` command followed by a jobId or job name.
For example, to delete job 12343:
```bash
qdel 12343
```

## Abaqus extras
Submit Abaqus jobs as usual from the command line:
```bash
abaqus job=whatever
```
This will invoke the `qdir_submit.py` module to create a job script and submit it to qdir.

You may submit jobs within Abaqus CAE by selecting `qdir` as the Job's queue before submitting.
You may check the queue status within CAE in the menu `Plug-ins > QDir Job Queue Monitor...`
Click on a Job to see more detailed information.
Right-click on a Job to expose the menu allowing you to delete the Job.

## Customization
Most parameters used by the script may be customized with command line options, system environment variables, or directives within the job file itself.

| Option | Description | Default |
|--------|-------------|---------|
| -N *NAME*, --name *NAME*  | Name for the job. | The last argument of the command |
| -q *QUEUE*, --queue *QUEUE* | Directory to store the queue files. | environment variable `QDIR_QUEUE` or `/tmp` on Linux |
| -c *INTERVAL*, --interval *INTERVAL* | Polling interval in seconds. | environment variable `QDIR_POLL_INTERVAL` or 5 |
| -i *INFO*, --info *INFO*  | Specify the format of information about jobs in queue | environment variable `QDIR_INFO` or `{jobId:8} {owner:12} {status:35} {name}` |
| -o *OUTPUT*, --output *OUTPUT* | File name for combined stdout and stderr. | environment variable `QDIR_LOGNAME` or `{name}._{jobId}`
| -s *STATUS*, --status *STATUS* | Specify the format of job status messages output to terminal. | environment variable `QDIR_STATUS` or `{jobId} {name} {status} after {duration}`
| -v *VERBOSE*, --verbose *VERBOSE* | Set the verbosity level. | environment variable `QDIR_VERBOSE` or 2 |
