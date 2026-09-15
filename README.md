# qdir
This implements a very low overhead first-in, first-out job queue for the local machine

The queue is maintained as a directory of tiny job queue files.
When a new job is submitted, this script will identify any existing job queue files and then add its own queue file to the directory.
No job will begin until all the preceeding queue files are gone.
Each job will delete its own queue file upon completion so the next job can begin.
A shared queue directory should be specified on a multi-user system.
On Linux this is `/tmp` by default.

Any command may be submitted to the queue.
Some extras are provided as a convenience for Abaqus users.

# Installation
Requires python3, Windows or Linux

Download and unzip the [latest release](https://github.com/costerwi/qdir/releases/latest)

## Command line
To use command line tools `qsub`, `qstat`, `qdel`, add the installation directory to your system PATH.

## Abaqus extras
1. For Abaqus, move the files to a convenient `abaqus_plugins` directory, such as `C:\Users\You\abaqus_plugins\qdir\`
2. Add the following lines to your Abaqus `custom_v6.env` file:
```python
import sys
sys.path.append(r"C:/path/to/here/")  # directory of qdirAbaqus.py
import qdirAbaqus
qdirAbaqus.init(queues)
run_mode = BATCH
```

# Usage
## Command line
Submit commands or scripts to the queue using the command `qsub`.
On Linux:
```
qsub ./myJobFile.sh
```
On Windows:
```
qsub myJobFile.cmd
```

Check status with the `qstat` command.
Delete or kill jobs with the `qdel` command.
Display command options with `qsub -h`

## Abaqus extras
Submit Abaqus jobs as usual from the command line:
```
abaqus job=whatever
```
The `qdirAbaqus.py` module will create a job script and submit the script to qdir.

You may submit jobs within CAE by selecting `qdir` as the Job's queue before submitting.
You may check the queue status within CAE in the menu `Plug-ins > QDir Job Queue Monitor...`
Click on a Job to see more information.
Right-click on a Job to expose the Delete option.

