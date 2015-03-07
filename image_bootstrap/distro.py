# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

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

        self._abs_mountpoint = None
        self._abs_first_partition_device = None
        self._first_partition_uuid = None

    def _partition_device(self):
        cmd_mklabel = [
                'parted',
                '--script',
                self._abs_target_path,
                'mklabel', 'msdos',
                ]
        self._executor.check_call(cmd_mklabel)

        cmd_mkpart = [
                'parted',
                '--script',
                self._abs_target_path,
                'mkpart', 'primary', 'ext4', '0%', '100%',
                ]
        self._executor.check_call(cmd_mkpart)

        cmd_boot_flag = [
                'parted',
                '--script',
                self._abs_target_path,
                'set', '1', 'boot', 'on',
                ]
        self._executor.check_call(cmd_boot_flag)

    def _kpartx_minus_a(self):
        cmd_list = [
                'kpartx',
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
                'kpartx',
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
                'mkfs.ext4',
                self._abs_first_partition_device,
                ]
        self._executor.check_call(cmd)

    def _mkdir_mountpount(self):
        self._abs_mountpoint = tempfile.mkdtemp(dir=_MOUNTPOINT_PARENT_DIR)

    def _mount_disk_chroot_mounts(self):
        cmd = [
                'mount',
                self._abs_first_partition_device,
                self._abs_mountpoint,
                ]
        self._executor.check_call(cmd)

    def run_directory_bootstrap(self):
        raise NotImplementedError()

    def _gather_first_partition_uuid(self):
        cmd_blkid = [
                'blkid',
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

    def _fix_grub_cfg_root_device(self):
        cmd_sed = [
                'sed',
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
                    'mount',
                    source,
                    ] \
                    + options \
                    + [
                        os.path.join(self._abs_mountpoint, target),
                    ]
            self._executor.check_call(cmd)

    def _install_grub(self):
        cmd = [
                'grub-install',
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
                'cp',
                '/etc/resolv.conf',
                os.path.join(self._abs_mountpoint, 'etc/resolv.conf'),
                ]
        self._executor.check_call(cmd)

    def _copy_chroot_scripts(self):
        abs_path_parent = os.path.join(self._abs_mountpoint, _CHROOT_SCRIPT_TARGET_DIR)
        cmd_mkdir = [
                'mkdir',
                abs_path_parent,
                ]
        self._executor.check_call(cmd_mkdir)
        for basename in os.listdir(self._abs_scripts_dir_chroot):
            abs_path_source = os.path.join(self._abs_scripts_dir_chroot, basename)
            abs_path_target = os.path.join(self._abs_mountpoint, _CHROOT_SCRIPT_TARGET_DIR, basename)
            cmd_copy = [
                    'cp',
                    abs_path_source,
                    abs_path_target,
                    ]
            self._executor.check_call(cmd_copy)
            cmd_chmod = [
                    'chmod',
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
                    'chroot',
                    self._abs_mountpoint,
                    os.path.join('/', _CHROOT_SCRIPT_TARGET_DIR, basename),
                    ]
            self._executor.check_call(cmd_run, env=env)

    def _remove_chroot_scripts(self):
        for basename in os.listdir(self._abs_scripts_dir_chroot):
            abs_path_target = os.path.join(self._abs_mountpoint, _CHROOT_SCRIPT_TARGET_DIR, basename)
            cmd_rm = [
                    'rm',
                    abs_path_target,
                    ]
            self._executor.check_call(cmd_rm)

        abs_path_parent = os.path.join(self._abs_mountpoint, _CHROOT_SCRIPT_TARGET_DIR)
        cmd_rmdir = [
                'rmdir',
                abs_path_parent,
                ]
        self._executor.check_call(cmd_rmdir)

    def _try_unmounting(self, abs_path):
        cmd = [
                'umount',
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
                'kpartx',
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
                    self._create_etc_fstab()
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
                    self._run_post_scripts()
                finally:
                    self._unmount_disk_chroot_mounts()
            finally:
                self._kpartx_minus_d()
        finally:
            self._rmdir_mountpount()
