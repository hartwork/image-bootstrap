# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later



import errno
import os
import subprocess
from abc import ABCMeta, abstractmethod
from textwrap import dedent

from directory_bootstrap.shared.commands import (
        COMMAND_FIND, COMMAND_UNAME, COMMAND_UNSHARE)
from image_bootstrap.distros.base import DISTRO_CLASS_FIELD, DistroStrategy
from image_bootstrap.engine import (
        BOOTLOADER__ANY_GRUB, BOOTLOADER__HOST_EXTLINUX, COMMAND_CHROOT)


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


class DebianBasedDistroStrategy(DistroStrategy, metaclass=ABCMeta):
    def __init__(self,
            messenger,
            executor,

            release,
            mirror_url,
            command_debootstrap,
            debootstrap_opt,
            ):
        self._messenger = messenger
        self._executor = executor

        self._release = release
        self._mirror_url = mirror_url
        self._command_debootstrap = command_debootstrap
        self._debootstrap_opt = debootstrap_opt

    @abstractmethod
    def check_release(self):
        pass

    def get_commands_to_check_for(self):
        return [
                    COMMAND_CHROOT,
                    COMMAND_FIND,
                    COMMAND_UNAME,
                    COMMAND_UNSHARE,
                    self._command_debootstrap,
                ]

    @abstractmethod
    def get_kernel_package_name(self, architecture):
        pass

    def check_architecture(self, architecture):
        uname_output = subprocess.check_output([COMMAND_UNAME, '-m'])
        host_machine = uname_output.rstrip()

        trouble = False
        if architecture == 'amd64' and host_machine != 'x86_64':
            trouble = True
        elif architecture == 'i386':
            if host_machine not in ('i386', 'i486', 'i586', 'i686', 'x86_64'):
                trouble = True

        if trouble:
            raise _ArchitectureMachineMismatch(architecture, host_machine)

        return architecture

    def configure_hostname(self, hostname):
        self.write_etc_hostname(hostname)

    def allow_autostart_of_services(self, allow):
        policy_rc_d_path = os.path.join(self._abs_mountpoint, 'usr/sbin/policy-rc.d')

        verb_activate = 'Re-activating' if allow else 'Deactivating'
        verb_create = 'removing' if allow else 'writing'
        self._messenger.info('%s auto-starting of services from package installations (by %s file "%s")...'
                % (verb_activate, verb_create, policy_rc_d_path))

        if allow:
            try:
                os.remove(policy_rc_d_path)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise
        else:
            # https://people.debian.org/~hmh/invokerc.d-policyrc.d-specification.txt
            with open(policy_rc_d_path, 'w') as f:
                print(dedent("""\
                        #! /bin/sh
                        exit 101
                        """), file=f)
                os.fchmod(f.fileno(), 0o755)

    def run_directory_bootstrap(self, architecture, bootloader_approach):
        self._messenger.info('Bootstrapping %s "%s" into "%s"...'
                % (self.DISTRO_NAME_SHORT, self._release, self._abs_mountpoint))

        _extra_packages = [
                'initramfs-tools',  # for update-initramfs
                self.get_kernel_package_name(architecture),
                ]
        if bootloader_approach in BOOTLOADER__ANY_GRUB:
            _extra_packages.append('grub-pc')
        elif bootloader_approach == BOOTLOADER__HOST_EXTLINUX:
            pass
        else:
            raise NotImplementedError('Unsupported bootloader for %s' % self.DISTRO_NAME_SHORT)

        cmd = [
                COMMAND_UNSHARE,
                '--mount',
                '--',
                self._command_debootstrap,
                '--arch', architecture,
                '--include=%s' % ','.join(_extra_packages),
                ] \
                + self._debootstrap_opt \
                + [
                self._release,
                self._abs_mountpoint,
                self._mirror_url,
                ]
        self._executor.check_call(cmd)

    def create_network_configuration(self, use_mtu_tristate):
        filename = os.path.join(self._abs_mountpoint, 'etc', 'network', 'interfaces')
        self._messenger.info('Writing file "%s"...' % filename)
        f = open(filename, 'w')
        print(_ETC_NETWORK_INTERFACES_CONTENT, file=f)
        f.close()

        # TODO For non-None use_mtu_tristate, force DHCP client option 26/interface-mtu
        use_mtu_tristate

    def ensure_chroot_has_grub2_installed(self):
        pass  # debootstrap has already pulled GRUB 2.x in

    def get_chroot_command_grub2_install(self):
        return 'grub-install'

    def generate_grub_cfg_from_inside_chroot(self):
        cmd = [
                COMMAND_CHROOT,
                self._abs_mountpoint,
                'update-grub',
                ]
        self._executor.check_call(cmd, env=self.create_chroot_env())

    def generate_initramfs_from_inside_chroot(self):
        cmd = [
                COMMAND_CHROOT,
                self._abs_mountpoint,
                'update-initramfs',
                '-u',
                '-k', 'all',
                ]
        self._executor.check_call(cmd, env=self.create_chroot_env())

    def perform_in_chroot_shipping_clean_up(self):
        pass  # nothing, yet

    def perform_post_chroot_clean_up(self):
        self._messenger.info('Cleaning chroot apt cache...')
        cmd = [
                COMMAND_FIND,
                os.path.join(self._abs_mountpoint, 'var', 'cache', 'apt', 'archives'),
                '-type', 'f',
                '-name', '*.deb',
                '-delete',
                ]
        self._executor.check_call(cmd)

    def _install_packages(self, package_names):
        self._messenger.info('Installing %s...' % ', '.join(package_names))
        env = self.create_chroot_env()
        env.setdefault('DEBIAN_FRONTEND', 'noninteractive')
        cmd = [
                COMMAND_CHROOT,
                self._abs_mountpoint,
                'apt-get',
                'install',
                '-y', '--no-install-recommends', '-V',
                ] + list(package_names)
        self._executor.check_call(cmd, env=env)

    def install_dhcp_client(self):
        pass  # already installed

    def install_sudo(self):
        self._install_packages(['sudo'])

    @abstractmethod
    def install_cloud_init_and_friends(self):
        pass

    def get_cloud_init_datasource_cfg_path(self):
        return '/etc/cloud/cloud.cfg.d/90_dpkg.cfg'  # existing file

    def install_sshd(self):
        self._install_packages(['openssh-server'])

    def make_openstack_services_autostart(self):
        pass  # autostarted in Debian, already

    def get_vmlinuz_path(self):
        return '/vmlinuz'

    def get_initramfs_path(self):
        return '/initrd.img'

    def install_kernel(self):
        pass  # Kernel installed, already

    def install_acpid(self):
        self._install_packages(['acpid'])

    @classmethod
    def add_parser_to(clazz, distros):
        debian = distros.add_parser(clazz.DISTRO_KEY, help=clazz.DISTRO_NAME_LONG)
        debian.set_defaults(**{DISTRO_CLASS_FIELD: clazz})

        debian_commands = debian.add_argument_group('command names')
        debian_commands.add_argument('--debootstrap', metavar='COMMAND',
                dest='command_debootstrap', default='debootstrap',
                help='override debootstrap command')

        debian.add_argument('--release', dest='release', default=clazz.DEFAULT_RELEASE,
                metavar='RELEASE',
                help='specify %s release (default: %%(default)s)'
                % clazz.DISTRO_NAME_SHORT)
        debian.add_argument('--mirror', dest='mirror_url', metavar='URL',
                default=clazz.DEFAULT_MIRROR_URL,
                help='specify %s mirror to use (e.g. %s for '
                    'a local instance of apt-cacher-ng; default: %%(default)s)'
                    % (clazz.DISTRO_NAME_SHORT, clazz.APT_CACHER_NG_URL))

        debian.add_argument('--debootstrap-opt', dest='debootstrap_opt',
                metavar='OPTION', action='append', default=[],
                help='option to pass to debootstrap, in addition; '
                    'can be passed several times; '
                    'use with --debootstrap-opt=... syntax, i.e. with "="')

    @classmethod
    def create(clazz, messenger, executor, options):
        return clazz(
                messenger,
                executor,
                options.release,
                options.mirror_url,
                options.command_debootstrap,
                options.debootstrap_opt,
                )
