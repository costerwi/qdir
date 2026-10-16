"""Install or uninstall qdir for Abaqus.

This script will modify the user's abaqus_v6.env file with
settings for the qdir job queue.
"""

from __future__ import print_function, with_statement  # use Python3 syntax

import os
import sys
from argparse import ArgumentParser

settings = """# Settings for qdir job queue
sys.path.append(r"{}")  # directory of qdir_submit.py
import qdir_submit
qdir_submit.init(queues)
plugin_central_dir += os.pathsep + qdir_submit.dirname
run_mode = BATCH  # command line will submit to queue by default"""

parser = ArgumentParser(description=__doc__)
parser.add_argument(
    "action",
    choices=["install", "uninstall"],
    help="Specify what to do.",
)
default = os.path.expanduser("~/abaqus_v6.env")
parser.add_argument(
    "env",
    nargs="?",
    default=default,
    help="Optionally specify the .env file to modify. Default is {}".format(default),
)


def uninstall(user_env):
    """Remove qdir settings from user's abaqus_v6.env"""
    new_env = user_env + ".new"
    with open(new_env, "w") as new_env_file:
        try:
            # copy current settings
            with open(user_env) as env_file:
                for line in env_file:
                    if not "qdir" in line:  # skip any qdir settings
                        print(line.rstrip(), file=new_env_file)
            os.remove(user_env)
        except FileNotFoundError:
            pass
    os.rename(new_env, user_env)


def install(user_env):
    """Append qdir settings to user's abaqus_v6.env"""
    uninstall(user_env)  # remove any previous settings
    dirname = os.path.dirname(os.path.normpath(__file__))
    with open(user_env, "a") as user_env_file:
        print(settings.format(dirname), file=user_env_file)


if __name__ == "__main__":
    options = parser.parse_args(sys.argv[1:])
    if "uninstall" == options.action:
        print("Removing qdir settings from", options.env)
        uninstall(options.env)
    else:
        print("Adding qdir settings to", options.env)
        install(options.env)
