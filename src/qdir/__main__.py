#!/bin/env python3
"""Check qdir installation

This short script is meant to be invoked as `python3 -m qdir` and will check
for the availability of qsub, qstat, and qdel in the user's PATH.
"""

import os
import shutil
import sysconfig
from pathlib import Path

from qdir import __url__, __version__

scripts = 'qsub', 'qstat', 'qdel'

print("QDir job queue version", __version__, __url__)
found = list(shutil.which(script) for script in scripts)
if all(found):
    print("Installation looks good. All scripts were found in PATH:")
    for p in found:
        print("\t", str(p))
else:
    for scheme in sysconfig.get_scheme_names():
        p = sysconfig.get_path("scripts", scheme)
        if not p:
            continue
        found = (shutil.which(script, path=p) for script in scripts)
        if all(found):
            print("Scripts found here:\n", p)
            print("Add the above directory to your PATH in order to use commands", *scripts)
            break
    else:
        print("The scripts directory was not found.")
