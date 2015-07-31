# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from directory_bootstrap.shared.commands import (
        COMMAND_UMOUNT, check_call__keep_trying)


def try_unmounting(executor, abs_path):
    cmd = [
            COMMAND_UMOUNT,
            abs_path,
            ]
    check_call__keep_trying(executor, cmd)
