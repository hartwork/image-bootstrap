# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import errno
import os
import subprocess
import time

COMMAND_BLKID = 'blkid'
COMMAND_BLOCKDEV = 'blockdev'
COMMAND_CHMOD = 'chmod'
COMMAND_CHROOT = 'chroot'
COMMAND_CP = 'cp'
COMMAND_DB_DUMP = 'db_dump'
COMMAND_EXTLINUX = 'extlinux'
COMMAND_FILE = 'file'
COMMAND_FIND = 'find'
COMMAND_GPG = 'gpg'
COMMAND_INSTALL_MBR = 'install-mbr'
COMMAND_KPARTX = 'kpartx'
COMMAND_LSB_RELEASE = 'lsb_release'
COMMAND_MD5SUM = 'md5sum'
COMMAND_MKDIR = 'mkdir'
COMMAND_MKFS_EXT4 = 'mkfs.ext4'
COMMAND_MOUNT = 'mount'
COMMAND_PARTED = 'parted'
COMMAND_PARTPROBE = 'partprobe'
COMMAND_RM = 'rm'
COMMAND_RMDIR = 'rmdir'
COMMAND_RPM = 'rpm'
COMMAND_SED = 'sed'
COMMAND_SHA512SUM = 'sha512sum'
COMMAND_TAR = 'tar'
COMMAND_TUNE2FS = 'tune2fs'
COMMAND_UMOUNT = 'umount'
COMMAND_UNAME = 'uname'
COMMAND_UNSHARE = 'unshare'
COMMAND_UNXZ = 'unxz'
COMMAND_WGET = 'wget'
COMMAND_YUM = 'yum'


EXIT_COMMAND_NOT_FOUND = 127


def check_call__keep_trying(executor, cmd):
	for i in range(3):
		try:
			executor.check_call(cmd)
		except subprocess.CalledProcessError as e:
			if e.returncode == EXIT_COMMAND_NOT_FOUND:
				raise
			time.sleep(1)
		else:
			break


def find_command(command):
    assert not command.startswith('/')

    dirs = os.environ['PATH'].split(':')
    for _dir in dirs:
        abs_path = os.path.join(_dir, command)
        if os.path.exists(abs_path):
            return abs_path

    raise OSError(EXIT_COMMAND_NOT_FOUND, 'Command "%s" not found in PATH.' \
        % command)


def check_for_commands(messenger, commands_to_check_for):
    infos_produced = False

    missing_files = []
    missing_commands = []
    for command in sorted(set(c for c in commands_to_check_for if c is not None)):
        if command.startswith('/'):
            abs_path = command
            if not os.path.exists(abs_path):
                missing_files.append(abs_path)
            continue

        try:
            abs_path = find_command(command)
        except OSError as e:
            if e.errno != EXIT_COMMAND_NOT_FOUND:
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
        raise OSError(EXIT_COMMAND_NOT_FOUND, 'Command "%s" not found in PATH.' \
            % missing_commands[0])

    if infos_produced:
        messenger.info_gap()
