# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import errno
import os


EXIT_COMMAND_NOT_FOUND = 127


def find_command(command):
    dirs = os.environ['PATH'].split(':')
    for _dir in dirs:
        abs_path = os.path.join(_dir, command)
        if os.path.exists(abs_path):
            return abs_path

    raise OSError(_EXIT_COMMAND_NOT_FOUND, 'Command "%s" not found in PATH.' \
        % command)


def check_for_commands(messenger, commands_to_check_for):
    infos_produced = False

    missing_files = []
    missing_commands = []
    for command in sorted(set(commands_to_check_for)):
        if command is None:
            continue

        if command.startswith('/'):
            abs_path = command
            if not os.path.exists(abs_path):
                missing_files.append(abs_path)
            continue

        assert not command.startswith('/')
        try:
            abs_path = find_command(command)
        except OSError as e:
            if e.errno != _EXIT_COMMAND_NOT_FOUND:
                raise
            missing_commands.append(command)
            messenger.error('Checking for %s... NOT FOUND' % command)
        else:
            messenger.info('Checking for %s... %s' % (command, abs_path))
            infos_produced = True

    if missing_files:
        raise OSError(errno.ENOENT, 'File "%s" not found.' \
            % missing_files[0])

    if missing_commands:
        raise OSError(_EXIT_COMMAND_NOT_FOUND, 'Command "%s" not found in PATH.' \
            % missing_commands[0])

    if infos_produced:
        messenger.info_gap()
