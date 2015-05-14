# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import os
import subprocess

from image_bootstrap.distro import \
        BootstrapDistroAgnostic, COMMAND_CHROOT, \
        BOOTLOADER__AUTO, \
        BOOTLOADER__CHROOT_GRUB2__DRIVE, \
        BOOTLOADER__HOST_GRUB2__DRIVE, \
        BOOTLOADER__NONE


_COMMAND_FIND = 'find'
_COMMAND_UNAME = 'uname'
_COMMAND_UNSHARE = 'unshare'


_ETC_NETWORK_INTERFACES_CONTENT = """\
# interfaces(5) file used by ifup(8) and ifdown(8)
auto lo
iface lo inet loopback

allow-hotplug eth0
iface eth0 inet dhcp
"""


class _ArchitectureMachineMismatch(Exception):
    def __init__(self, architecure, machine):
        self._architecture = architecure
        self._machine = machine

    def __str__(self):
        return 'Bootstrapping architecture %s on %s machines not supported' \
            % (self._architecture, self._machine)


class BootstrapDebian(BootstrapDistroAgnostic):
    DISTRO_KEY = 'debian'

    def __init__(self,
            messenger,
            executor,
            hostname,
            architecture,
            root_password,
            abs_root_password_file,
            abs_etc_resolv_conf,
            disk_id,
            first_partition_uuid,
            debian_release,
            debian_mirror_url,
            abs_scripts_dir_pre,
            abs_scripts_dir_chroot,
            abs_scripts_dir_post,
            abs_target_path,
            command_grub2_install,
            command_debootstrap,
            debootstrap_opt,
            bootloader_approach,
            bootloader_force,
            ):
        super(BootstrapDebian, self).__init__(
                messenger,
                executor,
                hostname,
                architecture,
                root_password,
                abs_root_password_file,
                abs_etc_resolv_conf,
                disk_id,
                first_partition_uuid,
                abs_scripts_dir_pre,
                abs_scripts_dir_chroot,
                abs_scripts_dir_post,
                abs_target_path,
                command_grub2_install,
                bootloader_force,
                )
        self._release = debian_release
        self._mirror_url = debian_mirror_url
        self._command_debootstrap = command_debootstrap
        self._debootstrap_opt = debootstrap_opt
        self._bootloader_approach = bootloader_approach

    def select_bootloader(self):
        if self._bootloader_approach == BOOTLOADER__AUTO:
            self._bootloader_approach = BOOTLOADER__CHROOT_GRUB2__DRIVE
            self._messenger.info('Selected approach "%s" for bootloader installation.'
                    % self._bootloader_approach)

    def get_commands_to_check_for(self):
        return iter(
                list(super(BootstrapDebian, self).get_commands_to_check_for())
                + [
                    COMMAND_CHROOT,
                    _COMMAND_FIND,
                    _COMMAND_UNAME,
                    _COMMAND_UNSHARE,
                    self._command_debootstrap,
                ])

    def _get_kernel_package_name(self):
        if self._architecture == 'i386':
            return 'linux-image-686-pae'

        return 'linux-image-%s' % self._architecture

    def check_architecture(self):
        super(BootstrapDebian, self).check_architecture()

        uname_output = subprocess.check_output([_COMMAND_UNAME, '-m'])
        host_machine = uname_output.rstrip()

        trouble = False
        if self._architecture == 'amd64' and host_machine != 'x86_64':
            trouble = True
        elif self._architecture == 'i386':
            if host_machine not in ('i386', 'i486', 'i586', 'i686', 'x86_64'):
                trouble = True

        if trouble:
            raise _ArchitectureMachineMismatch(self._architecture, host_machine)

    def run_directory_bootstrap(self):
        self._messenger.info('Bootstrapping Debian into "%s"...' % self._abs_mountpoint)

        _extra_packages = [
                'initramfs-tools',  # for update-initramfs
                self._get_kernel_package_name(),
                ]
        if self._bootloader_approach != BOOTLOADER__NONE:
            _extra_packages.append('grub-pc')

        cmd = [
                _COMMAND_UNSHARE,
                '--mount',
                '--',
                self._command_debootstrap,
                '--arch', self._architecture,
                '--include=%s' % ','.join(_extra_packages),
                ] \
                + self._debootstrap_opt \
                + [
                self._release,
                self._abs_mountpoint,
                self._mirror_url,
                ]
        self._executor.check_call(cmd)

    def create_network_configuration(self):
        filename = os.path.join(self._abs_mountpoint, 'etc', 'network', 'interfaces')
        self._messenger.info('Writing file "%s"...' % filename)
        f = open(filename, 'w')
        print(_ETC_NETWORK_INTERFACES_CONTENT, file=f)
        f.close()

    def get_chroot_command_grub2_install(self):
        return 'grub-install'

    def generate_grub_cfg_from_inside_chroot(self):
        cmd = [
                COMMAND_CHROOT,
                self._abs_mountpoint,
                'update-grub',
                ]
        env = self.make_environment(tell_mountpoint=False)
        self._executor.check_call(cmd, env=env)

    def generate_initramfs_from_inside_chroot(self):
        cmd = [
                COMMAND_CHROOT,
                self._abs_mountpoint,
                'update-initramfs',
                '-u',
                '-k', 'all',
                ]
        env = self.make_environment(tell_mountpoint=False)
        self._executor.check_call(cmd, env=env)

    def perform_post_chroot_clean_up(self):
        self._messenger.info('Cleaning chroot apt cache...')
        cmd = [
                _COMMAND_FIND,
                os.path.join(self._abs_mountpoint, 'var', 'cache', 'apt', 'archives'),
                '-type', 'f',
                '-name', '*.deb',
                '-delete',
                ]
        self._executor.check_call(cmd)
