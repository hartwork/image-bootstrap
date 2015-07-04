# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import subprocess
import sys


class Executor(object):
    def __init__(self, messenger, stdout=None, stderr=None):
        self._messenger = messenger
        self._announce_target = stdout or sys.stdout
        self._default_stdout = stdout or sys.stdout
        self._default_stderr = stdout or sys.stderr

    def check_call(self, argv, env=None, cwd=None):
        self._messenger.announce_command(argv)
        subprocess.check_call(argv,
                stdout=self._default_stdout,
                stderr=self._default_stderr,
                env=env,
                cwd=cwd,
                )

    def check_output(self, argv):
        self._messenger.announce_command(argv)
        return subprocess.check_output(argv, stderr=self._default_stderr)
