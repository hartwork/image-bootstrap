# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import errno
import os
import pwd
import stat
import subprocess
import tempfile
import time
from textwrap import dedent

from directory_bootstrap.shared.byte_size import format_byte_size
from directory_bootstrap.shared.commands import (
        COMMAND_BLKID, COMMAND_BLOCKDEV, COMMAND_CHMOD, COMMAND_CHROOT,
        COMMAND_CP, COMMAND_EXTLINUX, COMMAND_FIND, COMMAND_INSTALL_MBR,
        COMMAND_KPARTX, COMMAND_MKDIR, COMMAND_MKFS_EXT4, COMMAND_MOUNT,
        COMMAND_PARTED, COMMAND_PARTPROBE, COMMAND_RM, COMMAND_RMDIR,
        COMMAND_SED, COMMAND_TUNE2FS, EXIT_COMMAND_NOT_FOUND,
        check_call__keep_trying, check_for_commands, find_command)
from directory_bootstrap.shared.mount import COMMAND_UMOUNT, try_unmounting
from directory_bootstrap.shared.namespace import (
        set_hostname, unshare_current_process)
from directory_bootstrap.shared.resolv_conf import filter_copy_resolv_conf
from image_bootstrap.boot_loaders.grub2 import (
        BOOTLOADER__CHROOT_GRUB2, BOOTLOADER__CHROOT_GRUB2__DEVICE,
        BOOTLOADER__CHROOT_GRUB2__DRIVE, BOOTLOADER__HOST_GRUB2__DEVICE,
        BOOTLOADER__HOST_GRUB2__DRIVE, GrubTwoInstaller)
from image_bootstrap.mount import MountFinder
from image_bootstrap.types.uuid import require_valid_uuid

BOOTLOADER__AUTO = 'auto'
BOOTLOADER__HOST_EXTLINUX = 'host-extlinux'
BOOTLOADER__NONE = 'none'


BOOTLOADER__ANY_GRUB = (
        BOOTLOADER__CHROOT_GRUB2__DEVICE,
        BOOTLOADER__CHROOT_GRUB2__DRIVE,
        BOOTLOADER__HOST_GRUB2__DEVICE,
        BOOTLOADER__HOST_GRUB2__DRIVE,
        )
BOOTLOADER__HOST_GRUB2 = (
        BOOTLOADER__HOST_GRUB2__DEVICE,
        BOOTLOADER__HOST_GRUB2__DRIVE,
        )


_MOUNTPOINT_PARENT_DIR = '/mnt'
_CHROOT_SCRIPT_TARGET_DIR = 'root/chroot-scripts/'

_NON_DISK_MOUNT_TASKS = (
        ('/dev', ['-o', 'bind'], 'dev'),
        ('/dev/pts', ['-o', 'bind'], 'dev/pts'),
        ('TMPFS', ['-t', 'tmpfs', '-o', 'mode=1777'], 'dev/shm'),
        ('PROC', ['-t', 'proc'], 'proc'),
        ('/sys', ['-o', 'bind'], 'sys'),
        )

_DISK_ID_OFFSET = 440
_DISK_ID_COUNT_BYTES = 4

_CONSOLE_CONFIG = 'console=tty0 console=ttyS0,115200'


class _script_filename_telling_exceptions(object):
    """
    Extends raised exceptions by filename of the causing script
    """
    def __init__(self, abs_script_filename):
        self._abs_script_filename = abs_script_filename

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            exc_val._ib_abs_script_filename = self._abs_script_filename


class MachineConfig(object):
    def __init__(self,
            hostname,
            architecture,
            root_password,
            abs_root_password_file,
            abs_etc_resolv_conf,
            disk_id,
            first_partition_uuid,
            machine_id,
            bootloader_approach,
            bootloader_force,
            with_openstack,
            ):
        self.hostname = hostname
        self.architecture = architecture
        self.root_password = root_password
        self.abs_root_password_file = abs_root_password_file
        self.abs_etc_resolv_conf = abs_etc_resolv_conf
        self.disk_id = disk_id
        self.first_partition_uuid = first_partition_uuid
        self.machine_id = machine_id
        self.bootloader_approach = bootloader_approach
        self.bootloader_force = bootloader_force
        self.with_openstack = with_openstack


class BootstrapEngine(object):
    def __init__(self,
            messenger,
            executor,
            machine_config,
            abs_scripts_dir_pre,
            abs_scripts_dir_chroot,
            abs_scripts_dir_post,
            abs_target_path,
            command_grub2_install,
            ):
        self._messenger = messenger
        self._executor = executor

        assert isinstance(machine_config, MachineConfig)
        self._config = machine_config

        self._abs_scripts_dir_pre = abs_scripts_dir_pre
        self._abs_scripts_dir_chroot = abs_scripts_dir_chroot
        self._abs_scripts_dir_post = abs_scripts_dir_post
        self._abs_target_path = abs_target_path

        self._command_grub2_install = command_grub2_install

        self._abs_mountpoint = None
        self._abs_first_partition_device = None

        self._distro = None

    def set_distro(self, distro):
        distro.set_chroot_env_prototype(self.make_environment(tell_mountpoint=False))
        self._distro = distro

    def check_release(self):
        return self._distro.check_release()

    def select_bootloader(self):
        if self._config.bootloader_approach == BOOTLOADER__AUTO:
            self._config.bootloader_approach = self._distro.select_bootloader()
            self._messenger.info('Selected approach "%s" for bootloader installation.'
                    % self._config.bootloader_approach)

    def get_commands_to_check_for(self):
        res = list(self._distro.get_commands_to_check_for())
        res += [
                COMMAND_BLKID,
                COMMAND_BLOCKDEV,
                COMMAND_CHMOD,
                COMMAND_CHROOT,
                COMMAND_CP,
                COMMAND_FIND,
                COMMAND_KPARTX,
                COMMAND_MKDIR,
                COMMAND_MKFS_EXT4,
                COMMAND_MOUNT,
                COMMAND_PARTED,
                COMMAND_PARTPROBE,
                COMMAND_RM,
                COMMAND_RMDIR,
                COMMAND_SED,
                COMMAND_TUNE2FS,
                COMMAND_UMOUNT,
                self._command_grub2_install,
                ]

        if self._config.bootloader_approach == BOOTLOADER__HOST_EXTLINUX:
            res += [
                    COMMAND_EXTLINUX,
                    COMMAND_INSTALL_MBR,
                    ]

        return res

    def _protect_against_grub_legacy(self, command):
        output = subprocess.check_output([command, '--version'])
        if 'GRUB GRUB 0.' in output:
            raise ValueError('Command "%s" is GRUB legacy while GRUB 2 is needed. '
                    'Please install GRUB 2 or pass --grub2-install .. on the command line.' \
                    % command)

    def detect_grub2_install(self):
        if self._command_grub2_install:
            return  # Explicit command given, no detection needed

        if self._config.bootloader_approach not in BOOTLOADER__HOST_GRUB2:
            return  # Host grub2-install not used, no detection needed

        COMMAND_GRUB_INSTALL = 'grub-install'
        COMMAND_GRUB2_INSTALL = 'grub2-install'

        self._command_grub2_install = COMMAND_GRUB2_INSTALL
        try:
            find_command(self._command_grub2_install)
        except OSError as e:
            if e.errno != EXIT_COMMAND_NOT_FOUND:
                raise

            self._command_grub2_install = COMMAND_GRUB_INSTALL
            try:
                find_command(self._command_grub2_install)
            except OSError as e:
                if e.errno != EXIT_COMMAND_NOT_FOUND:
                    raise

                # NOTE: consecutive search for "grub-install" will fail and
                #       be reported, so we don't need to raise here
                return

            self._protect_against_grub_legacy(self._command_grub2_install)

    def check_for_commands(self):
        check_for_commands(self._messenger, self.get_commands_to_check_for())

    def check_target_block_device(self):
        self._messenger.info('Checking if "%s" is a block device...' % self._abs_target_path)
        props = os.stat(self._abs_target_path)
        if not stat.S_ISBLK(props.st_mode):
            raise OSError(errno.ENOTBLK, 'Not a block device: "%s"' % self._abs_target_path)

    def check_architecture(self):
        self._messenger.info('Checking for known unsupported architecture/machine combination...')
        self._config.architecture = self._distro.check_architecture(self._config.architecture)
        assert self._config.architecture is not None

    def _script_should_be_run(self, basename):
        if basename.startswith('.'):
            return False
        elif basename.endswith('~'):
            return False
        return True

    def check_script_permissions(self):
        infos_produced = False

        good_uids = set()
        good_uids.add(os.geteuid())
        try:
            sudo_uid = int(os.environ['SUDO_UID'])
        except (KeyError, ValueError):
            pass
        else:
            good_uids.add(sudo_uid)

        for category, abs_scripts_dir in (
                ('pre-chroot', self._abs_scripts_dir_pre),
                ('chroot', self._abs_scripts_dir_chroot),
                ('post-chroot', self._abs_scripts_dir_post),
                ):
            if abs_scripts_dir is None:
                continue

            self._messenger.info('Checking %s scripts directory permissions...' % category)
            infos_produced = True

            props = os.lstat(abs_scripts_dir)
            if stat.S_ISLNK(props.st_mode):
                raise OSError(errno.ENOTDIR, 'Directory "%s" is a symlink. Only true directories are supported.' % abs_scripts_dir)

            if not stat.S_ISDIR(props.st_mode):
                raise OSError(errno.ENOTDIR, 'Directory "%s" is not a directory' % abs_scripts_dir)

            if props.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                raise OSError(errno.EPERM, 'Directory "%s" is writable to users other than its owner' % abs_scripts_dir)

            if props.st_uid not in good_uids:
                user_info = ' or '.join(('user %s/%d' % (pwd.getpwuid(uid).pw_name, uid) for uid in sorted(good_uids)))
                raise OSError(errno.EPERM, 'Directory "%s" is not owned by %s' % (abs_scripts_dir, user_info))

            self._messenger.info('Checking %s scripts for executability...' % category)
            infos_produced = True

            for basename in sorted(os.listdir(abs_scripts_dir)):
                if not self._script_should_be_run(basename):
                    continue

                abs_filename = os.path.join(abs_scripts_dir, basename)
                if not os.access(abs_filename, os.X_OK):
                    raise OSError(errno.EACCES, 'Permission denied, file "%s" not executable' % abs_filename)

        if infos_produced:
            self._messenger.info_gap()

    def _unshare(self):
        unshare_current_process(self._messenger)
        set_hostname(self._config.hostname)

    def _check_device_size(self):
        self._messenger.info('Checking size of "%s"...' % self._abs_target_path)
        blockdev_output = self._executor.check_output([
                COMMAND_BLOCKDEV,
                '--getsize64',
                self._abs_target_path,
                ])
        size_bytes_found = int(blockdev_output)
        size_bytes_needed = self._distro.get_minimum_size_bytes()
        if size_bytes_found < size_bytes_needed:
            raise OSError(errno.ENOSPC, 'Device "%s" is %s in size, %s or more needed.' % (
                    self._abs_target_path,
                    format_byte_size(size_bytes_found),
                    format_byte_size(size_bytes_needed),
                    ))

    def _partition_device(self):
        self._messenger.info('Partitioning "%s"...' % self._abs_target_path)
        cmd_mklabel = [
                COMMAND_PARTED,
                '--script',
                self._abs_target_path,
                'mklabel', 'msdos',
                ]
        self._executor.check_call(cmd_mklabel)

        # Make existing partition devices leave
        check_call__keep_trying(self._executor, [
                COMMAND_PARTPROBE,
                self._abs_target_path,
                ])

        cmd_mkpart = [
                COMMAND_PARTED,
                '--script',
                '--align', 'optimal',
                self._abs_target_path,
                'mkpart',
                'primary', 'ext4', '1', '100%',
                ]
        self._executor.check_call(cmd_mkpart)

        cmd_boot_flag = [
                COMMAND_PARTED,
                '--script',
                self._abs_target_path,
                'set', '1', 'boot', 'on',
                ]
        time.sleep(1)  # increase chances of first call working, e.g. with LVM volumes
        check_call__keep_trying(self._executor, cmd_boot_flag)

    def _create_partition_devices(self):
        self._messenger.info('Activating partition devices...')
        cmd_list = [
                COMMAND_KPARTX,
                '-l',
                self._abs_target_path,
                ]
        output = self._executor.check_output(cmd_list)
        device_name = output.split('\n')[0].split(' : ')[0]
        self._abs_first_partition_device = '/dev/mapper/%s' % device_name

        # NOTE: Ubuntu 15.04 does not have "-u" (issue #30)
        #       So we try -u first, then -a if -u failed
        try:
            self._executor.check_call([COMMAND_KPARTX,
                    '-u', self._abs_target_path,
                    ])
        except subprocess.CalledProcessError:
            self._executor.check_call([COMMAND_KPARTX,
                    '-a', self._abs_target_path,
                    ])

        for i in range(3):
            if os.path.exists(self._abs_first_partition_device):
                break
            time.sleep(1)
        else:
            raise OSError(errno.ENOENT, "No such block device file: '%s'" \
                    % self._abs_first_partition_device)

    def _format_partitions(self):
        self._messenger.info('Creating file system on "%s"...' % self._abs_first_partition_device)
        cmd = [
                COMMAND_MKFS_EXT4,
                '-F',
        ]

        if self._config.bootloader_approach == BOOTLOADER__HOST_EXTLINUX:
            self._messenger.warn('Creating ext4 file system with '
                    'feature "64bit" disabled '
                    'to ensure bootability with extlinux.')
            self._messenger.warn('Please see '
                    'https://github.com/hartwork/image-bootstrap/issues/44'
                    ' for details.')
            cmd += ['-O', '^64bit']

        cmd += self._distro.get_extra_mkfs_ext4_options()

        cmd += [
                self._abs_first_partition_device,
                ]
        self._executor.check_call(cmd)

    def _mkdir_mountpount(self):
        self._abs_mountpoint = tempfile.mkdtemp(dir=_MOUNTPOINT_PARENT_DIR)
        self._messenger.info('Creating directory "%s"...' % self._abs_mountpoint)
        self._distro.set_mountpoint(self._abs_mountpoint)

    def _mkdir_mountpount_etc(self):
        abs_dir = os.path.join(self._abs_mountpoint, 'etc')
        self._messenger.info('Creating directory "%s"...' % abs_dir)
        os.mkdir(abs_dir, 0755)

    def _mount_disk_chroot_mounts(self):
        self._messenger.info('Mounting partitions...')
        cmd = [
                COMMAND_MOUNT,
                self._abs_first_partition_device,
                self._abs_mountpoint,
                ]
        self._executor.check_call(cmd)

    def run_directory_bootstrap(self):
        return self._distro.run_directory_bootstrap(
                self._config.architecture,
                self._config.bootloader_approach,
                )

    def _unmount_directory_bootstrap_leftovers(self):
        mounts = MountFinder()
        mounts.load()
        for abs_mount_point in reversed(list(mounts.below(self._abs_mountpoint))):
            self._try_unmounting(abs_mount_point)

    def _set_root_password_inside_chroot(self):
        self._messenger.info('Setting root password...')
        if self._config.root_password is None:
            return

        cmd = [
                COMMAND_CHROOT,
                self._abs_mountpoint,
                'chpasswd',
                ]
        env = self.make_environment(tell_mountpoint=False)
        self._messenger.announce_command(cmd)
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, env=env)
        p.stdin.write('root:%s' % self._config.root_password)
        p.stdin.close()
        p.wait()
        if p.returncode:
            raise subprocess.CalledProcessError(p.returncode, cmd)

    def _set_first_partition_uuid(self):
        if not self._config.first_partition_uuid:
            return

        self._messenger.info('Setting first partition UUID to %s...' % self._config.first_partition_uuid)
        cmd = [COMMAND_TUNE2FS,
                '-U', self._config.first_partition_uuid,
                self._abs_first_partition_device,
                ]
        self._executor.check_call(cmd)

    def _gather_first_partition_uuid(self):
        cmd_blkid = [
                COMMAND_BLKID,
                '-o', 'value',
                '-s', 'UUID',
                self._abs_first_partition_device,
                ]
        output = self._executor.check_output(cmd_blkid)
        first_partition_uuid = output.rstrip()
        require_valid_uuid(first_partition_uuid)
        self._config.first_partition_uuid = first_partition_uuid

    def _create_etc_fstab(self):
        filename = os.path.join(self._abs_mountpoint, 'etc', 'fstab')
        self._messenger.info('Writing file "%s"...' % filename)
        f = open(filename, 'w')
        print('/dev/disk/by-uuid/%s / auto defaults 0 1' % self._config.first_partition_uuid, file=f)
        f.close()

    def _create_etc_machine_id(self):
        if self._config.machine_id:
            etc_machine_id = os.path.join(self._abs_mountpoint, 'etc/machine-id')
            self._messenger.info('Writing file "%s"...' % etc_machine_id)
            with open(etc_machine_id, 'w') as f:
                print(self._config.machine_id, file=f)

    def _configure_hostname(self):
        self._distro.configure_hostname(self._config.hostname)

    def create_network_configuration(self):
        use_mtu_tristate = True if self._config.with_openstack else None
        return self._distro.create_network_configuration(use_mtu_tristate)

    def _fix_grub_cfg_root_device(self):
        self._messenger.info('Post-processing GRUB config...')
        cmd_sed = [
                COMMAND_SED,
                's,root=[^ ]\+,root=UUID=%s,g' % self._config.first_partition_uuid,
                '-i', os.path.join(self._abs_mountpoint, 'boot', 'grub', 'grub.cfg'),
                ]
        self._executor.check_call(cmd_sed)

    def _run_scripts_from(self, abs_scripts_dir, env):
        for basename in sorted(os.listdir(abs_scripts_dir)):
            if not self._script_should_be_run(basename):
                continue

            abs_script_filename = os.path.join(abs_scripts_dir, basename)
            cmd = [abs_script_filename]
            with _script_filename_telling_exceptions(abs_script_filename):
                self._executor.check_call(cmd, env=env.copy())

    def make_environment(self, tell_mountpoint):
        env = os.environ.copy()
        for key in ('LANG', 'LANGUAGE'):
            env.pop(key, None)

        assert self._config.hostname is not None
        env.update({
                'HOSTNAME': self._config.hostname,  # for compatibility to grml-debootstrap
                'IB_HOSTNAME': self._config.hostname,
                'LC_ALL': 'C',
                })

        if tell_mountpoint:
            assert self._abs_mountpoint is not None
            env.update({
                    'IB_ROOT': self._abs_mountpoint,
                    'MNTPOINT': self._abs_mountpoint,  # for compatibility to grml-debootstrap
                    })

        return env

    def _run_pre_scripts(self):
        self._messenger.info('Running pre-chroot scripts...')
        env = self.make_environment(tell_mountpoint=True)
        if self._abs_scripts_dir_pre:
            self._run_scripts_from(self._abs_scripts_dir_pre, env)

    def _mount_nondisk_chroot_mounts(self):
        self._messenger.info('Mounting non-disk file systems...')
        for source, options, target in _NON_DISK_MOUNT_TASKS:
            cmd = [
                    COMMAND_MOUNT,
                    source,
                    ] \
                    + options \
                    + [
                        os.path.join(self._abs_mountpoint, target),
                    ]
            self._executor.check_call(cmd)

    def get_chroot_command_grub2_install(self):
        return self._distro.get_chroot_command_grub2_install()

    def _ensure_chroot_has_grub2_installed(self):
        self._distro.ensure_chroot_has_grub2_installed()

    def _install_bootloader__extlinux(self):
        assert self._config.first_partition_uuid
        d = {
            'distro_key': self._distro.DISTRO_KEY,
            'distro_name_long': self._distro.DISTRO_NAME_LONG,
            'kernel_extra': (' %s' % _CONSOLE_CONFIG) if self._config.with_openstack else '',
            'uuid': self._config.first_partition_uuid,
            'vmlinuz': self._distro.get_vmlinuz_path(),
            'initramfs': self._distro.get_initramfs_path(),
        }

        boot_extlinux = os.path.join(self._abs_mountpoint, 'boot/extlinux/')
        extlinux_conf = os.path.join(boot_extlinux, 'extlinux.conf')

        os.makedirs(boot_extlinux)

        self._messenger.info('Writing file "%s"...' % extlinux_conf)
        with open(extlinux_conf, 'w') as f:
            print(dedent("""\
                    DEFAULT  %(distro_key)s
                    TIMEOUT  1

                    LABEL    %(distro_key)s
                    SAY      Booting %(distro_name_long)s...
                    KERNEL   %(vmlinuz)s
                    APPEND   initrd=%(initramfs)s root=/dev/disk/by-uuid/%(uuid)s%(kernel_extra)s
                    INITRD   %(initramfs)s
                    """ % d), file=f)

        self._messenger.info('Installing extlinux to "%s"...' % boot_extlinux)
        cmd_extlinux = [
                COMMAND_EXTLINUX,
                '--install',
                boot_extlinux,
                ]
        self._executor.check_call(cmd_extlinux)

        self._messenger.info('Writing MBR of "%s"...' % self._abs_target_path)
        cmd_mbr = [
                COMMAND_INSTALL_MBR,
                '--force',
                self._abs_target_path,
                ]
        self._executor.check_call(cmd_mbr)

    def _install_bootloader__grub2(self):
        installer = GrubTwoInstaller(
                self._messenger,
                self._executor,
                self._abs_target_path,
                self._config.bootloader_approach,
                self._config.bootloader_force,
                self._command_grub2_install,
                self.get_chroot_command_grub2_install(),
                self.make_environment(tell_mountpoint=False),
                self._abs_mountpoint,
                )
        installer.run()

    def adjust_grub_defaults(self):
        res = self._distro.adjust_grub_defaults(self._config.with_openstack)

        if self._config.with_openstack:
            self._messenger.info('Enabling serial console...')
            env = self.make_environment(tell_mountpoint=False)
            self._executor.check_call([
                    COMMAND_CHROOT, self._abs_mountpoint,
                    'sed',
                    's:^\\(GRUB_CMDLINE_LINUX="[^"]*\\)":\\1 %s":'
                            % _CONSOLE_CONFIG,
                    '-i', '/etc/default/grub',
                    ], env=env)

        return res

    def generate_grub_cfg_from_inside_chroot(self):
        return self._distro.generate_grub_cfg_from_inside_chroot()

    def _adjust_initramfs_generator_config(self):
        self._distro.adjust_initramfs_generator_config()

    def generate_initramfs_from_inside_chroot(self):
        self._messenger.info('Generating initramfs...')
        return self._distro.generate_initramfs_from_inside_chroot()

    def _create_etc_resolv_conf(self):
        output_filename = os.path.join(self._abs_mountpoint, 'etc', 'resolv.conf')

        filter_copy_resolv_conf(self._messenger, self._config.abs_etc_resolv_conf, output_filename)

    def _copy_chroot_scripts(self):
        self._messenger.info('Copying chroot scripts into chroot...')
        abs_path_parent = os.path.join(self._abs_mountpoint, _CHROOT_SCRIPT_TARGET_DIR)
        cmd_mkdir = [
                COMMAND_MKDIR,
                abs_path_parent,
                ]
        self._executor.check_call(cmd_mkdir)
        for basename in os.listdir(self._abs_scripts_dir_chroot):
            if not self._script_should_be_run(basename):
                continue

            abs_path_source = os.path.join(self._abs_scripts_dir_chroot, basename)
            abs_path_target = os.path.join(self._abs_mountpoint, _CHROOT_SCRIPT_TARGET_DIR, basename)
            cmd_copy = [
                    COMMAND_CP,
                    abs_path_source,
                    abs_path_target,
                    ]
            self._executor.check_call(cmd_copy)
            cmd_chmod = [
                    COMMAND_CHMOD,
                    'a+x',
                    abs_path_target,
                    ]
            self._executor.check_call(cmd_chmod)

    def _run_chroot_scripts(self):
        self._messenger.info('Running chroot scripts...')
        env = self.make_environment(tell_mountpoint=False)
        for basename in sorted(os.listdir(self._abs_scripts_dir_chroot)):
            if not self._script_should_be_run(basename):
                continue

            abs_script_filename = os.path.join(
                    self._abs_scripts_dir_chroot, basename)
            cmd_run = [
                    COMMAND_CHROOT,
                    self._abs_mountpoint,
                    os.path.join('/', _CHROOT_SCRIPT_TARGET_DIR, basename),
                    ]
            with _script_filename_telling_exceptions(abs_script_filename):
                self._executor.check_call(cmd_run, env=env.copy())

    def _remove_chroot_scripts(self):
        self._messenger.info('Removing chroot scripts...')
        for basename in os.listdir(self._abs_scripts_dir_chroot):
            if not self._script_should_be_run(basename):
                continue

            abs_path_target = os.path.join(self._abs_mountpoint, _CHROOT_SCRIPT_TARGET_DIR, basename)
            cmd_rm = [
                    COMMAND_RM,
                    abs_path_target,
                    ]
            self._executor.check_call(cmd_rm)

        abs_path_parent = os.path.join(self._abs_mountpoint, _CHROOT_SCRIPT_TARGET_DIR)
        cmd_rmdir = [
                COMMAND_RMDIR,
                abs_path_parent,
                ]
        self._executor.check_call(cmd_rmdir)

    def _try_unmounting(self, abs_path):
        return try_unmounting(self._executor, abs_path)

    def _unmount_nondisk_chroot_mounts(self):
        self._messenger.info('Unmounting non-disk file systems...')
        for source, options, target in reversed(_NON_DISK_MOUNT_TASKS):
            abs_path = os.path.join(self._abs_mountpoint, target)
            self._try_unmounting(abs_path)

    def _perform_in_chroot_shipping_clean_up(self):
        self._distro.perform_in_chroot_shipping_clean_up()

    def perform_post_chroot_clean_up(self):
        return self._distro.perform_post_chroot_clean_up()

    def _run_post_scripts(self):
        self._messenger.info('Running post-chroot scripts...')
        env = self.make_environment(tell_mountpoint=True)
        if self._abs_scripts_dir_post:
            self._run_scripts_from(self._abs_scripts_dir_post, env)

    def _unmount_disk_chroot_mounts(self):
        self._messenger.info('Unmounting partitions...')
        self._try_unmounting(self._abs_mountpoint)

    def _remove_partition_devices(self):
        self._messenger.info('Deactivating partition devices...')
        cmd = [
                COMMAND_KPARTX,
                '-d',
                self._abs_target_path,
                ]
        check_call__keep_trying(self._executor, cmd)

    def _rmdir_mountpount(self):
        self._messenger.info('Removing directory "%s"...' % self._abs_mountpoint)
        for i in range(3):
            try:
                os.rmdir(self._abs_mountpoint)
            except OSError as e:
                if e.errno != errno.EBUSY:
                    raise
                time.sleep(1)
            else:
                break

    def _set_disk_id_in_mbr(self):
        if not self._config.disk_id:
            return

        content = self._config.disk_id.byte_sequence()
        assert len(content) == _DISK_ID_COUNT_BYTES

        self._messenger.info('Setting MBR disk identifier to %s (4 bytes)...' % str(self._config.disk_id))
        f = open(self._abs_target_path, 'w')
        f.seek(_DISK_ID_OFFSET)
        f.write(content)
        f.close()

    def process_root_password(self):
        if self._config.abs_root_password_file:
            self._messenger.info('Reading root password from file "%s"...' % self._config.abs_root_password_file)
            f = open(self._config.abs_root_password_file)
            self._config.root_password = f.read().split('\n')[0]
            f.close()
        elif self._config.root_password is not None:
            self._messenger.warn('Using --password PASSWORD is a security risk more often than not; '
                    'please consider using --password-file FILE, instead.')

    def _install_dhcp_client(self):
        return self._distro.install_dhcp_client()

    def _install_sudo(self):
        return self._distro.install_sudo()

    def _create_sudo_nopasswd_user(self):
        user_name = self._distro.get_cloud_username()
        self._messenger.info('Creating user "%s"...' % user_name)
        cmd = [
                COMMAND_CHROOT,
                self._abs_mountpoint,
                'useradd',
                '--comment', 'Cloud-init-user',
                '--base-dir', '/home',
                '--create-home',
                '--shell', '/bin/bash',
                '--user-group', user_name,
                ]
        env = self.make_environment(tell_mountpoint=False)
        self._executor.check_call(cmd, env)

        self._messenger.info('Allowing user "%s" to call sudo with no password...' % user_name)
        sudoers_path = os.path.join(self._abs_mountpoint, 'etc/sudoers.d/%s-nopasswd' % user_name)
        with open(sudoers_path, 'w') as f:
            print('%s ALL = NOPASSWD: ALL' % user_name, file=f)
            os.fchmod(f.fileno(), 0440)

    def _install_cloud_init_and_friends(self):
        self._distro.install_cloud_init_and_friends()

    def _configure_cloud_init_and_friends(self):
        self._distro.adjust_etc_cloud_cfg()

        cloud_cfg_d_file_path = os.path.join(self._abs_mountpoint,
                self._distro.get_cloud_init_datasource_cfg_path().lstrip('/'))
        self._messenger.info('Writing file "%s"...' % cloud_cfg_d_file_path)
        with open(cloud_cfg_d_file_path, 'w') as f:
            print(dedent("""\
                    # generated by image-bootstrap
                    datasource_list: [ConfigDrive, NoCloud, Openstack, Ec2]
                    """), file=f)

    def _install_sshd(self):
        return self._distro.install_sshd()

    def _delete_sshd_keys(self):
        # Even with new keys generated by cloud-init, it would
        # be cool to not have the current keys go into the image.
        #
        # May not affect all distros, some may not generate them
        # before the SSH server is started, e.g. Arch
        self._messenger.info('Deleting SSH server keys (if any)...')
        cmd = [
                COMMAND_FIND,
                os.path.join(self._abs_mountpoint, 'etc/ssh/'),
                '-type', 'f',
                '-name', 'ssh_host_*key*',
                '-delete', '-print',
                ]
        self._executor.check_call(cmd)

    def _clean_machine_id(self):
        dbus_machine_id = os.path.join(self._abs_mountpoint, 'var/lib/dbus/machine-id')
        try:
            os.remove(dbus_machine_id)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
        else:
            self._messenger.info('Removing file "%s"...' % dbus_machine_id)

        if not self._config.machine_id:  # i.e. keep if explicit ID requested
            etc_machine_id = os.path.join(self._abs_mountpoint, 'etc/machine-id')
            self._messenger.info('Truncating file "%s"...' % etc_machine_id)
            with open(etc_machine_id, 'w') as f:
                f.truncate(0)

    def _make_openstack_services_autostart(self):
        return self._distro.make_openstack_services_autostart()

    def _disable_clearing_tty1(self):
        noclear_file_path = os.path.join(self._abs_mountpoint, 'etc/systemd/system/getty@tty1.service.d/noclear.conf')
        self._messenger.info('Disabling clearing of tty1 (file "%s")...' % noclear_file_path)
        os.makedirs(os.path.dirname(noclear_file_path), 0755)
        with open(noclear_file_path, 'w') as f:
            print(dedent("""\
                    [Service]
                    TTYVTDisallocate=no
                    """), file=f)

    def _disable_pcspkr_autoloading(self):
        file_name = os.path.join(self._abs_mountpoint, 'etc/modprobe.d/pcspkr_no_autoload.conf')
        self._messenger.info('Disabling auto-loading of pcspkr kernel module...')
        with open(file_name, 'w') as f:
            print(dedent("""\
                # disable auto-loading of pcspkr module, by image-bootstrap
                blacklist pcspkr
                """), file=f)

    def _install_acpid_unless_using_systemd(self):
        if not self._distro.uses_systemd():
            return self._distro.install_acpid()

    def _allow_autostart_of_services(self, allow):
        # The idea is to avoid starting services in the chroot
        # that we would only need to kill one way or another
        self._distro.allow_autostart_of_services(allow)

    def _prepare_installation_of_packages(self):
        self._distro.prepare_installation_of_packages()

    def _install_kernel(self):
        self._distro.install_kernel()

    def _turn_etc_resolv_conf_to_systemd_resolved(self):
        self._messenger.info('Handing /etc/resolv.conf over to systemd-resolved...')
        os.remove(os.path.join(self._abs_mountpoint, 'etc', 'resolv.conf'))
        env = self.make_environment(tell_mountpoint=False)
        self._executor.check_call([
                COMMAND_CHROOT, self._abs_mountpoint,
                'ln', '-s', '/run/systemd/resolve/resolv.conf', '/etc/resolv.conf',
                ], env=env)

    def run(self):
        self._unshare()
        self._check_device_size()
        self._partition_device()
        self._set_disk_id_in_mbr()
        self._create_partition_devices()
        try:
            self._format_partitions()

            if self._config.first_partition_uuid:
                self._set_first_partition_uuid()
            else:
                self._gather_first_partition_uuid()
            assert self._config.first_partition_uuid

            self._mkdir_mountpount()
            try:
                self._mount_disk_chroot_mounts()
                try:
                    self._mkdir_mountpount_etc()
                    self._configure_hostname()  # first time
                    self._create_etc_resolv_conf()  # first time
                    try:
                        self.run_directory_bootstrap()
                    finally:
                        self._unmount_directory_bootstrap_leftovers()
                    self._configure_hostname()  # re-write
                    self._create_etc_resolv_conf()  # re-write
                    self._create_etc_fstab()
                    self._create_etc_machine_id()  # potentially re-write
                    self._run_pre_scripts()
                    if self._config.bootloader_approach in BOOTLOADER__HOST_GRUB2:
                        self._install_bootloader__grub2()
                    elif self._config.bootloader_approach == BOOTLOADER__HOST_EXTLINUX:
                        self._install_bootloader__extlinux()
                    self._mount_nondisk_chroot_mounts()
                    try:
                        self._allow_autostart_of_services(False)
                        self._set_root_password_inside_chroot()
                        self._prepare_installation_of_packages()

                        # NOTE: Kernel is configured/installed early to allow other
                        #       packages to run their checks on the kernel configuration
                        #       with the actual kernel configuration
                        self._install_kernel()

                        if self._config.bootloader_approach in BOOTLOADER__ANY_GRUB:
                            # Need grub2-mkconfig in any case
                            self._ensure_chroot_has_grub2_installed()

                        if self._config.bootloader_approach in BOOTLOADER__CHROOT_GRUB2:
                            self._install_bootloader__grub2()

                        if self._config.with_openstack:
                            # Essentials
                            self._install_dhcp_client()
                            self._install_sudo()
                            self._install_cloud_init_and_friends()
                            self._configure_cloud_init_and_friends()
                            self._install_sshd()
                            self._make_openstack_services_autostart()

                            # Goodies
                            self._disable_clearing_tty1()
                            self._disable_pcspkr_autoloading()
                            self._install_acpid_unless_using_systemd()
                        # elif with vagrant support:
                        #   ...
                        #   self._install_sudo()
                        #   self._create_sudo_nopasswd_user()
                        #   ...

                        self.create_network_configuration()  # after DHCP client install

                        self._adjust_initramfs_generator_config()
                        self.generate_initramfs_from_inside_chroot()

                        if self._config.bootloader_approach in BOOTLOADER__ANY_GRUB:
                            self.adjust_grub_defaults()
                            self._messenger.info('Generating GRUB configuration...')
                            self.generate_grub_cfg_from_inside_chroot()
                            self._fix_grub_cfg_root_device()

                        if self._abs_scripts_dir_chroot:
                            self._copy_chroot_scripts()
                            try:
                                self._run_chroot_scripts()
                            finally:
                                self._remove_chroot_scripts()

                        if self._config.with_openstack:
                            # Essentials (that better go last)
                            self._delete_sshd_keys()
                            self._clean_machine_id()
                            self._perform_in_chroot_shipping_clean_up()

                            if self._distro.uses_systemd_resolved(self._config.with_openstack):
                                # Cannot go early, breaks chroot connectivity
                                self._turn_etc_resolv_conf_to_systemd_resolved()

                        self._allow_autostart_of_services(True)
                    finally:
                        self._unmount_nondisk_chroot_mounts()
                    self.perform_post_chroot_clean_up()
                    self._run_post_scripts()
                finally:
                    self._unmount_disk_chroot_mounts()
            finally:
                self._rmdir_mountpount()
        finally:
            self._remove_partition_devices()
