# qdir
A very low overhead first-in, first-out job queue for the local machine

This type of queue is ideal when you have multiple programs (jobs)
that must run sequentially rather than in parallel,
often due to resource constraints or dependencies.
For example, to run several finite element analysis models in sequence.
You can add jobs to the queue at any time,
monitor the current job list and remove specific jobs as necessary.
(see [usage](#usage) below)

The queue operates by maintaining a directory of small job status files.
When a new job is added, it creates its own status file and then
waits for all preceding files to clear before running its command.
By default, jobs check every 5 seconds for their turn to run.
Once a job finishes, it deletes its status file, allowing the next one to start.

The queue directory may be set to a shared location on multi-user systems
(`/tmp` by default in Linux)
in order to coordinate sequential execution among all users.

# Installation
Requires python3 on Windows, Linux, or MacOS.
One way to get python3 on Windows is through the
[Microsoft Store](https://apps.microsoft.com/detail/9PNRBTZXMB4Z).
Here is the command to install qdir once python3 is available:
```bash
python3 -m pip install qdir
```

See [installation of pip](https://pip.pypa.io/en/stable/installation/) if there is "no module named pip."

If there is a warning that the script directory is not in the PATH then
it must be added in order to use the command line tools.
Otherwise, [see below without modifying PATH](#usage-without-script-directory-in-path).

Check the installation with `python3 -m qdir`

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

Any printed output from the command (stdout and stderr) will be saved to a new
file whose name has the job Id appended to the end.

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
The jobId is a number matching its process ID.
This means on Linux you may terminate or remove a job from queue by
killing that process ID, for example, `kill 12343`
Also, deleting a job's status file will terminate or remove the job from queue.

## Usage without script directory in PATH
The `qsub`, `qstat`, and `qdel` scripts are shortcuts to call python3 methods.
These scripts will not be available at the command line if
the directory where pip installed them is not in the PATH.
It's most convenient to add this directory to the PATH but it is also
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
Right-click on a Job to open a popup menu allowing you to delete the Job.

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
