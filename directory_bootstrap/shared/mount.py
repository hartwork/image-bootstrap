# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import subprocess
import time


from directory_bootstrap.shared.commands import COMMAND_UMOUNT


def try_unmounting(executor, abs_path):
    cmd = [
            COMMAND_UMOUNT,
            abs_path,
            ]
    for i in range(3):
        try:
            executor.check_call(cmd)
        except subprocess.CalledProcessError:
            time.sleep(1)
        else:
            break
