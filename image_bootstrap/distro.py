# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import errno
import os
import re
import subprocess
import tempfile
import time


_MOUNTPOINT_PARENT_DIR = '/mnt'
_CHROOT_SCRIPT_TARGET_DIR = 'root/chroot-scripts/'

_NON_DISK_MOUNT_TASKS = (
        ('/dev', ['-o', 'bind'], 'dev'),
        ('/dev/pts', ['-o', 'bind'], 'dev/pts'),
        ('PROC', ['-t', 'proc'], 'proc'),
        ('/sys', ['-o', 'bind'], 'sys'),
        )

_SANE_UUID_CHECKER = re.compile('^[a-f0-9][a-f0-9-]{34}[a-f0-9]$')


_COMMAND_BLKID = 'blkid'
_COMMAND_CHMOD = 'chmod'
_COMMAND_CHPASSWD = 'chpasswd'
COMMAND_CHROOT = 'chroot'
_COMMAND_CP = 'cp'
_COMMAND_KPARTX = 'kpartx'
_COMMAND_MKDIR = 'mkdir'
_COMMAND_MKFS_EXT4 = 'mkfs.ext4'
_COMMAND_MOUNT = 'mount'
_COMMAND_PARTED = 'parted'
_COMMAND_RM = 'rm'
_COMMAND_RMDIR = 'rmdir'
_COMMAND_SED = 'sed'
_COMMAND_UMOUNT = 'umount'


class BootstrapDistroAgnostic(object):
    def __init__(self,
            messenger,
            executor,
            hostname,
            architecture,
            root_password,
            abs_scripts_dir_pre,
            abs_scripts_dir_chroot,
            abs_scripts_dir_post,
            abs_target_path,
            command_grub2_install,
            ):
        self._messenger = messenger
        self._executor = executor
        self._hostname = hostname
        self._architecture = architecture
        self._root_password = root_password
        self._abs_scripts_dir_pre = abs_scripts_dir_pre
        self._abs_scripts_dir_chroot = abs_scripts_dir_chroot
        self._abs_scripts_dir_post = abs_scripts_dir_post
        self._abs_target_path = abs_target_path

        self._command_grub2_install = command_grub2_install

        self._abs_mountpoint = None
        self._abs_first_partition_device = None
        self._first_partition_uuid = None

    def get_commands_to_check_for(self):
        return iter((
                _COMMAND_BLKID,
                _COMMAND_CHMOD,
                _COMMAND_CHPASSWD,
                COMMAND_CHROOT,
                _COMMAND_CP,
                _COMMAND_KPARTX,
                _COMMAND_MKDIR,
                _COMMAND_MKFS_EXT4,
                _COMMAND_MOUNT,
                _COMMAND_PARTED,
                _COMMAND_RM,
                _COMMAND_RMDIR,
                _COMMAND_SED,
                _COMMAND_UMOUNT,
                self._command_grub2_install,
                ))

    def check_for_commands(self):
        missing_files = []
        missing_commands = []
        dirs = os.environ['PATH'].split(':')
        for command in sorted(set(self.get_commands_to_check_for())):
            if command.startswith('/'):
                abs_path = command
                if not os.path.exists(abs_path):
                    missing_files.append(abs_path)
                continue

            assert not command.startswith('/')
            for _dir in dirs:
                abs_path = os.path.join(_dir, command)
                if os.path.exists(abs_path):
                    self._messenger.info('Checking for %s... %s' % (command, abs_path))
                    break
            else:
                missing_commands.append(command)
                self._messenger.error('Checking for %s... NOT FOUND' % command)

        if missing_files:
            raise OSError(errno.ENOENT, 'File "%s" not found.' \
                % missing_files[0])

        if missing_commands:
            raise OSError(errno.ENOENT, 'Command "%s" not found in PATH.' \
                % missing_commands[0])

    def _partition_device(self):
        cmd_mklabel = [
                _COMMAND_PARTED,
                '--script',
                self._abs_target_path,
                'mklabel', 'msdos',
                ]
        self._executor.check_call(cmd_mklabel)

        cmd_mkpart = [
                _COMMAND_PARTED,
                '--script',
                self._abs_target_path,
                'mkpart', 'primary', 'ext4', '0%', '100%',
                ]
        self._executor.check_call(cmd_mkpart)

        cmd_boot_flag = [
                _COMMAND_PARTED,
                '--script',
                self._abs_target_path,
                'set', '1', 'boot', 'on',
                ]
        self._executor.check_call(cmd_boot_flag)

    def _kpartx_minus_a(self):
        cmd_list = [
                _COMMAND_KPARTX,
                '-l',
                '-p', 'p',
                self._abs_target_path,
                ]
        output = self._executor.check_output(cmd_list)
        device_name = output.split('\n')[0].split(' : ')[0]
        self._abs_first_partition_device = '/dev/mapper/%s' % device_name

        if os.path.exists(self._abs_first_partition_device):
            raise XXXXXXXXXXXXXXXXXXXXXXXXX

        cmd_add = [
                _COMMAND_KPARTX,
                '-a',
                '-p', 'p',
                '-s',
                self._abs_target_path,
                ]
        self._executor.check_call(cmd_add)

        if not os.path.exists(self._abs_first_partition_device):
            raise XXXXXXXXXXXXXXXXXXXXXX

    def _format_partitions(self):
        cmd = [
                _COMMAND_MKFS_EXT4,
                self._abs_first_partition_device,
                ]
        self._executor.check_call(cmd)

    def _mkdir_mountpount(self):
        self._abs_mountpoint = tempfile.mkdtemp(dir=_MOUNTPOINT_PARENT_DIR)

    def _mount_disk_chroot_mounts(self):
        cmd = [
                _COMMAND_MOUNT,
                self._abs_first_partition_device,
                self._abs_mountpoint,
                ]
        self._executor.check_call(cmd)

    def run_directory_bootstrap(self):
        raise NotImplementedError()

    def _set_root_password(self):
        if self._root_password is None:
            return

        cmd = [
                _COMMAND_CHPASSWD,
                '--root', self._abs_mountpoint,
                ]
        self._messenger.announce_command(cmd)
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        p.stdin.write('root:%s' % self._root_password)
        p.stdin.close()
        p.wait()
        if p.returncode:
            raise subprocess.CalledProcessError(p.returncode, cmd)

    def _gather_first_partition_uuid(self):
        cmd_blkid = [
                _COMMAND_BLKID,
                '-o', 'value',
                '-s', 'UUID',
                self._abs_first_partition_device,
                ]
        output = self._executor.check_output(cmd_blkid)
        first_partition_uuid = output.rstrip()
        if not _SANE_UUID_CHECKER.match(first_partition_uuid):
            raise XXXXXXXXXXXXXXXXXXXXXX
        self._first_partition_uuid = first_partition_uuid

    def _create_etc_fstab(self):
        f = open(os.path.join(self._abs_mountpoint, 'etc', 'fstab'), 'w')
        print('/dev/disk/by-uuid/%s / auto defaults 0 1' % self._first_partition_uuid, file=f)
        f.close()

    def _create_etc_hostname(self):
        f = open(os.path.join(self._abs_mountpoint, 'etc', 'hostname'), 'w')
        print(self._hostname, file=f)
        f.close()

    def create_network_configuration(self):
        raise NotImplementedError()

    def _fix_grub_cfg_root_device(self):
        cmd_sed = [
                _COMMAND_SED,
                's,root=[^ ]\+,root=UUID=%s,g' % self._first_partition_uuid,
                '-i', os.path.join(self._abs_mountpoint, 'boot', 'grub', 'grub.cfg'),
                ]
        self._executor.check_call(cmd_sed)

    def _run_scripts_from(self, abs_scripts_dir, env):
        for basename in os.listdir(abs_scripts_dir):
            cmd = [os.path.join(abs_scripts_dir, basename)]
            self._executor.check_call(cmd, env=env)

    def _run_pre_scripts(self):
        env = {
                'HOSTNAME': self._hostname,
                'PATH': os.environ['PATH'],
                'MNTPOINT': self._abs_mountpoint,
                }
        if self._abs_scripts_dir_pre:
            self._run_scripts_from(self._abs_scripts_dir_pre, env)

    def _mount_nondisk_chroot_mounts(self):
        for source, options, target in _NON_DISK_MOUNT_TASKS:
            cmd = [
                    _COMMAND_MOUNT,
                    source,
                    ] \
                    + options \
                    + [
                        os.path.join(self._abs_mountpoint, target),
                    ]
            self._executor.check_call(cmd)

    def _install_grub(self):
        cmd = [
                self._command_grub2_install,
                '--boot-directory',
                os.path.join(self._abs_mountpoint, 'boot'),
                self._abs_target_path,
                ]
        self._executor.check_call(cmd)

    def generate_grub_cfg_from_inside_chroot(self):
        raise NotImplementedError()

    def generate_initramfs_from_inside_chroot(self):
        raise NotImplementedError()

    def _copy_resolv_conf(self):
        cmd = [
                _COMMAND_CP,
                '/etc/resolv.conf',
                os.path.join(self._abs_mountpoint, 'etc/resolv.conf'),
                ]
        self._executor.check_call(cmd)

    def _copy_chroot_scripts(self):
        abs_path_parent = os.path.join(self._abs_mountpoint, _CHROOT_SCRIPT_TARGET_DIR)
        cmd_mkdir = [
                _COMMAND_MKDIR,
                abs_path_parent,
                ]
        self._executor.check_call(cmd_mkdir)
        for basename in os.listdir(self._abs_scripts_dir_chroot):
            abs_path_source = os.path.join(self._abs_scripts_dir_chroot, basename)
            abs_path_target = os.path.join(self._abs_mountpoint, _CHROOT_SCRIPT_TARGET_DIR, basename)
            cmd_copy = [
                    _COMMAND_CP,
                    abs_path_source,
                    abs_path_target,
                    ]
            self._executor.check_call(cmd_copy)
            cmd_chmod = [
                    _COMMAND_CHMOD,
                    'a+x',
                    abs_path_target,
                    ]
            self._executor.check_call(cmd_chmod)

    def _run_chroot_scripts(self):
        env = {
                'HOSTNAME': self._hostname,
                'PATH': os.environ['PATH'],
                }
        for basename in os.listdir(self._abs_scripts_dir_chroot):
            cmd_run = [
                    COMMAND_CHROOT,
                    self._abs_mountpoint,
                    os.path.join('/', _CHROOT_SCRIPT_TARGET_DIR, basename),
                    ]
            self._executor.check_call(cmd_run, env=env)

    def _remove_chroot_scripts(self):
        for basename in os.listdir(self._abs_scripts_dir_chroot):
            abs_path_target = os.path.join(self._abs_mountpoint, _CHROOT_SCRIPT_TARGET_DIR, basename)
            cmd_rm = [
                    _COMMAND_RM,
                    abs_path_target,
                    ]
            self._executor.check_call(cmd_rm)

        abs_path_parent = os.path.join(self._abs_mountpoint, _CHROOT_SCRIPT_TARGET_DIR)
        cmd_rmdir = [
                _COMMAND_RMDIR,
                abs_path_parent,
                ]
        self._executor.check_call(cmd_rmdir)

    def _try_unmounting(self, abs_path):
        cmd = [
                _COMMAND_UMOUNT,
                abs_path,
                ]
        for i in range(3):
            try:
                self._executor.check_call(cmd)
            except subprocess.CalledProcessError as e:
                if e.returncode == 127:  # command not found
                    raise
                time.sleep(1)
            else:
                break

    def _unmount_nondisk_chroot_mounts(self):
        for source, options, target in reversed(_NON_DISK_MOUNT_TASKS):
            abs_path = os.path.join(self._abs_mountpoint, target)
            self._try_unmounting(abs_path)

    def perform_post_chroot_clean_up(self):
        raise NotImplementedError()

    def _run_post_scripts(self):
        env = {
                'PATH': os.environ['PATH'],
                'MNTPOINT': self._abs_mountpoint,
                }
        if self._abs_scripts_dir_post:
            self._run_scripts_from(self._abs_scripts_dir_post, env)

    def _unmount_disk_chroot_mounts(self):
        self._try_unmounting(self._abs_mountpoint)

    def _kpartx_minus_d(self):
        cmd = [
                _COMMAND_KPARTX,
                '-d',
                '-p', 'p',
                self._abs_target_path,
                ]
        self._executor.check_call(cmd)

    def _rmdir_mountpount(self):
        os.rmdir(self._abs_mountpoint)

    def run(self):
        self._partition_device()
        self._mkdir_mountpount()
        try:
            self._kpartx_minus_a()
            try:
                self._format_partitions()
                self._gather_first_partition_uuid()
                self._mount_disk_chroot_mounts()
                try:
                    self.run_directory_bootstrap()
                    self._set_root_password()
                    self._create_etc_fstab()
                    self._create_etc_hostname()
                    self.create_network_configuration()
                    self._run_pre_scripts()
                    self._install_grub()
                    self._mount_nondisk_chroot_mounts()
                    try:
                        self.generate_grub_cfg_from_inside_chroot()
                        self._fix_grub_cfg_root_device()
                        self.generate_initramfs_from_inside_chroot()
                        if self._abs_scripts_dir_chroot:
                            self._copy_resolv_conf()
                            self._copy_chroot_scripts()
                            try:
                                self._run_chroot_scripts()
                            finally:
                                self._remove_chroot_scripts()
                    finally:
                        self._unmount_nondisk_chroot_mounts()
                    self.perform_post_chroot_clean_up()
                    self._run_post_scripts()
                finally:
                    self._unmount_disk_chroot_mounts()
            finally:
                self._kpartx_minus_d()
        finally:
            self._rmdir_mountpount()
