# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import os
import subprocess

from image_bootstrap.engine import \
        COMMAND_CHROOT, \
        BOOTLOADER__AUTO, \
        BOOTLOADER__CHROOT_GRUB2__DRIVE, \
        BOOTLOADER__HOST_GRUB2__DRIVE, \
        BOOTLOADER__NONE


DISTRO_CLASS_FIELD = 'distro_class'

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


class DebianStrategy(object):
    DISTRO_KEY = 'debian'

    def __init__(self,
            messenger,
            executor,

            debian_release,
            debian_mirror_url,
            command_debootstrap,
            debootstrap_opt,
            ):
        self._messenger = messenger
        self._executor = executor

        self._release = debian_release
        self._mirror_url = debian_mirror_url
        self._command_debootstrap = command_debootstrap
        self._debootstrap_opt = debootstrap_opt

    def check_release(self):
        if self._release in ('stable', 'testing'):
            raise ValueError('For Debian releases, please use names like "jessie" rather than "%s".'
                % self._release)

    def select_bootloader(self):
        return BOOTLOADER__CHROOT_GRUB2__DRIVE

    def get_commands_to_check_for(self):
        return [
                    COMMAND_CHROOT,
                    _COMMAND_FIND,
                    _COMMAND_UNAME,
                    _COMMAND_UNSHARE,
                    self._command_debootstrap,
                ]

    def _get_kernel_package_name(self, architecture):
        if architecture == 'i386':
            return 'linux-image-686-pae'

        return 'linux-image-%s' % architecture

    def check_architecture(self, architecture):
        uname_output = subprocess.check_output([_COMMAND_UNAME, '-m'])
        host_machine = uname_output.rstrip()

        trouble = False
        if architecture == 'amd64' and host_machine != 'x86_64':
            trouble = True
        elif architecture == 'i386':
            if host_machine not in ('i386', 'i486', 'i586', 'i686', 'x86_64'):
                trouble = True

        if trouble:
            raise _ArchitectureMachineMismatch(architecture, host_machine)

    def run_directory_bootstrap(self, abs_mountpoint, architecture, bootloader_approach):
        self._messenger.info('Bootstrapping Debian "%s" into "%s"...'
                % (self._release, abs_mountpoint))

        _extra_packages = [
                'initramfs-tools',  # for update-initramfs
                self._get_kernel_package_name(architecture),
                ]
        if bootloader_approach != BOOTLOADER__NONE:
            _extra_packages.append('grub-pc')

        cmd = [
                _COMMAND_UNSHARE,
                '--mount',
                '--',
                self._command_debootstrap,
                '--arch', architecture,
                '--include=%s' % ','.join(_extra_packages),
                ] \
                + self._debootstrap_opt \
                + [
                self._release,
                abs_mountpoint,
                self._mirror_url,
                ]
        self._executor.check_call(cmd)

    def create_network_configuration(self, abs_mountpoint):
        filename = os.path.join(abs_mountpoint, 'etc', 'network', 'interfaces')
        self._messenger.info('Writing file "%s"...' % filename)
        f = open(filename, 'w')
        print(_ETC_NETWORK_INTERFACES_CONTENT, file=f)
        f.close()

    def get_chroot_command_grub2_install(self):
        return 'grub-install'

    def generate_grub_cfg_from_inside_chroot(self, abs_mountpoint, env):
        cmd = [
                COMMAND_CHROOT,
                abs_mountpoint,
                'update-grub',
                ]
        self._executor.check_call(cmd, env=env)

    def generate_initramfs_from_inside_chroot(self, abs_mountpoint, env):
        cmd = [
                COMMAND_CHROOT,
                abs_mountpoint,
                'update-initramfs',
                '-u',
                '-k', 'all',
                ]
        self._executor.check_call(cmd, env=env)

    def perform_post_chroot_clean_up(self, abs_mountpoint):
        self._messenger.info('Cleaning chroot apt cache...')
        cmd = [
                _COMMAND_FIND,
                os.path.join(abs_mountpoint, 'var', 'cache', 'apt', 'archives'),
                '-type', 'f',
                '-name', '*.deb',
                '-delete',
                ]
        self._executor.check_call(cmd)

    @classmethod
    def add_parser_to(clazz, distros):
        debian = distros.add_parser('debian', help='Debian GNU/Linux')
        debian.set_defaults(**{DISTRO_CLASS_FIELD: clazz})

        debian_commands = debian.add_argument_group('command names')
        debian_commands.add_argument('--debootstrap', metavar='COMMAND',
                dest='command_debootstrap', default='debootstrap',
                help='override debootstrap command')

        debian.add_argument('--release', dest='debian_release', default='jessie',
                metavar='RELEASE',
                help='specify Debian release (default: %(default)s)')
        debian.add_argument('--mirror', dest='debian_mirror_url', metavar='URL',
                default='http://http.debian.net/debian',
                help='specify Debian mirror to use (e.g. http://localhost:3142/debian for '
                    'a local instance of apt-cacher-ng; default: %(default)s)')

        debian.add_argument('--debootstrap-opt', dest='debootstrap_opt',
                metavar='OPTION', action='append', default=[],
                help='option to pass to debootstrap, in addition; '
                    'can be passed several times; '
                    'use with --debootstrap-opt=... syntax, i.e. with "="')

    @staticmethod
    def create(messenger, executor, options):
        return DebianStrategy(
                messenger,
                executor,
                options.debian_release,
                options.debian_mirror_url,
                options.command_debootstrap,
                options.debootstrap_opt,
                )
