# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later



import os
from textwrap import dedent

from pkg_resources import resource_filename

from directory_bootstrap.distros.arch import (
        SUPPORTED_ARCHITECTURES, ArchBootstrapper)
from directory_bootstrap.shared.commands import (
        COMMAND_CHROOT, COMMAND_CP, COMMAND_FIND, COMMAND_RM, COMMAND_SED,
        COMMAND_WGET)
from image_bootstrap.distros.base import DISTRO_CLASS_FIELD, DistroStrategy


class ArchStrategy(DistroStrategy):
    DISTRO_KEY = 'arch'
    DISTRO_NAME_SHORT = 'Arch'
    DISTRO_NAME_LONG = 'Arch Linux'

    def __init__(self, messenger, executor,
                abs_cache_dir, image_date_triple_or_none, mirror_url,
                abs_resolv_conf):
        super(ArchStrategy, self).__init__(
                messenger,
                executor,
                abs_cache_dir,
                abs_resolv_conf,
                )

        self._image_date_triple_or_none = image_date_triple_or_none
        self._mirror_url = mirror_url

    def get_commands_to_check_for(self):
        return ArchBootstrapper.get_commands_to_check_for() + [
                COMMAND_CHROOT,
                COMMAND_CP,
                COMMAND_FIND,
                COMMAND_RM,
                COMMAND_SED,
                COMMAND_WGET,
                ]

    def check_architecture(self, architecture):
        if architecture == 'amd64':
            architecture = 'x86_64'

        if architecture not in SUPPORTED_ARCHITECTURES:
            raise ValueError('Architecture "%s" not supported' % architecture)

        return architecture

    def configure_hostname(self, hostname):
        self.write_etc_hostname(hostname)

    def allow_autostart_of_services(self, allow):
        pass  # services are not auto-started on Arch

    def run_directory_bootstrap(self, architecture, bootloader_approach):
        self._messenger.info('Bootstrapping %s into "%s"...'
                % (self.DISTRO_NAME_SHORT, self._abs_mountpoint))

        bootstrap = ArchBootstrapper(
                self._messenger,
                self._executor,
                self._abs_mountpoint,
                self._abs_cache_dir,
                architecture,
                self._image_date_triple_or_none,
                self._mirror_url,
                self._abs_resolv_conf,
                )
        bootstrap.run()

    def create_network_configuration(self, use_mtu_tristate):
        self._messenger.info('Making sure that network interfaces get named eth*...')
        os.symlink('/dev/null', os.path.join(self._abs_mountpoint, 'etc/udev/rules.d/80-net-setup-link.rules'))

        network_filename = os.path.join(self._abs_mountpoint, 'etc/systemd/network/eth0-dhcp.network')
        self._messenger.info('Writing file "%s"...' % network_filename)
        with open(network_filename, 'w') as f:
            if use_mtu_tristate is None:
                print(dedent("""\
                        [Match]
                        Name=eth0

                        [Network]
                        DHCP=yes
                        """), file=f)
            else:
                d = {
                    'use_mtu': 'true' if use_mtu_tristate else 'false',
                }
                print(dedent("""\
                        [Match]
                        Name=eth0

                        [Network]
                        DHCP=yes

                        [DHCP]
                        UseMTU=%(use_mtu)s
                        """ % d), file=f)

    def _install_packages(self, package_names):
        cmd = [
                COMMAND_CHROOT,
                self._abs_mountpoint,
                'pacman',
                '--noconfirm',
                '--sync',
                ] + list(package_names)
        self._executor.check_call(cmd, env=self.create_chroot_env())

    def ensure_chroot_has_grub2_installed(self):
        self._install_packages(['grub'])

    def get_chroot_command_grub2_install(self):
        return 'grub-install'

    def generate_grub_cfg_from_inside_chroot(self):
        cmd = [
                COMMAND_CHROOT,
                self._abs_mountpoint,
                'grub-mkconfig',
                '-o', '/boot/grub/grub.cfg',
                ]
        self._executor.check_call(cmd, env=self.create_chroot_env())

    def adjust_initramfs_generator_config(self):
        abs_linux_preset = os.path.join(self._abs_mountpoint, 'etc', 'mkinitcpio.d', 'linux.preset')
        self._messenger.info('Adjusting "%s"...' % abs_linux_preset)
        cmd_sed = [
                COMMAND_SED,
                's,^[# \\t]*default_options=.*,default_options="-S autodetect"  # set by image-bootstrap,g',
                '-i', abs_linux_preset,
                ]
        self._executor.check_call(cmd_sed)

    def generate_initramfs_from_inside_chroot(self):
        cmd_mkinitcpio = [
                COMMAND_CHROOT,
                self._abs_mountpoint,
                'mkinitcpio',
                '-p', 'linux',
                ]
        self._executor.check_call(cmd_mkinitcpio, env=self.create_chroot_env())

    def _setup_pacman_reanimation(self):
        self._messenger.info('Installing haveged (for reanimate-pacman, only)...')
        self._install_packages(['haveged'])

        local_reanimate_path = '/usr/sbin/reanimate-pacman'

        full_reanimate_path = os.path.join(self._abs_mountpoint, local_reanimate_path.lstrip('/'))
        self._messenger.info('Writing file "%s"...' % full_reanimate_path)
        with open(full_reanimate_path, 'w') as f:
            print(dedent("""\
                    #! /bin/bash
                    if [[ -e /etc/pacman.d/gnupg ]]; then
                            exit 0
                    fi

                    haveged -F &
                    haveged_pid=$!

                    /usr/bin/pacman-key --init
                    /usr/bin/pacman-key --populate archlinux

                    kill -9 "${haveged_pid}"
                    """), file=f)
            os.fchmod(f.fileno(), 0o755)

        pacman_reanimation_service = os.path.join(self._abs_mountpoint,
                'etc/systemd/system/pacman-reanimation.service')
        self._messenger.info('Writing file "%s"...' % pacman_reanimation_service)
        with open(pacman_reanimation_service, 'w') as f:
            print(dedent("""\
                    [Unit]
                    Description=Pacman reanimation

                    [Service]
                    ExecStart=/bin/true
                    ExecStartPost=%s

                    [Install]
                    WantedBy=multi-user.target
                    """ % local_reanimate_path), file=f)

        self._make_services_autostart(['pacman-reanimation'])

    def perform_in_chroot_shipping_clean_up(self):
        self._setup_pacman_reanimation()

        # NOTE: After this, calling pacman needs reanimation, first
        pacman_gpg_path = os.path.join(self._abs_mountpoint, 'etc/pacman.d/gnupg')
        self._messenger.info('Deleting pacman keys at "%s"...' % pacman_gpg_path)
        cmd = [
                COMMAND_RM,
                '-Rv', pacman_gpg_path,
                ]
        self._executor.check_call(cmd)


    def perform_post_chroot_clean_up(self):
        self._messenger.info('Cleaning chroot pacman cache...')
        cmd = [
                COMMAND_FIND,
                os.path.join(self._abs_mountpoint, 'var/cache/pacman/pkg/'),
                '-type', 'f',
                '-delete',
                ]
        self._executor.check_call(cmd)

    def install_dhcp_client(self):
        pass  # already installed (part of systemd)

    def install_sudo(self):
        self._install_packages(['sudo'])

    def install_cloud_init_and_friends(self):
        self._install_packages(['cloud-init'])
        self.disable_cloud_init_syslog_fix_perms()
        self.install_growpart()

    def get_cloud_init_datasource_cfg_path(self):
        return '/etc/cloud/cloud.cfg.d/90_datasource.cfg'

    def install_sshd(self):
        self._install_packages(['openssh'])

    def _make_services_autostart(self, service_names):
        for service_name in service_names:
            self._messenger.info('Making service "%s" start automatically...' % service_name)
            cmd = [
                COMMAND_CHROOT,
                self._abs_mountpoint,
                'systemctl',
                'enable',
                service_name,
                ]
            self._executor.check_call(cmd, env=self.create_chroot_env())

    def make_openstack_services_autostart(self):
        self._make_services_autostart([
                'systemd-networkd',
                'systemd-resolved',  # for nameserver IPs from DHCP
                'sshd',
                'cloud-init-local',
                'cloud-init',
                'cloud-config',
                'cloud-final',
                ])

    def get_vmlinuz_path(self):
        return '/boot/vmlinuz-linux'

    def get_initramfs_path(self):
        return '/boot/initramfs-linux.img'

    def install_kernel(self):
        self._install_packages(['linux'])

    def adjust_cloud_cfg_dict(self, cloud_cfg_dict):
        super(ArchStrategy, self).adjust_cloud_cfg_dict(cloud_cfg_dict)

        # Get rid of groups cdrom, dailout, dip, netdev, plugdev, sudo.
        # https://github.com/hartwork/image-bootstrap/issues/49#issuecomment-317191835
        # https://bugs.archlinux.org/task/54911
        system_info = cloud_cfg_dict.setdefault('system_info', {})
        system_info__default_user = system_info.setdefault('default_user', {})
        system_info__default_user['groups'] = ['adm']

    def uses_systemd(self):
        return True

    def uses_systemd_resolved(self, with_openstack):
        return with_openstack

    def get_minimum_size_bytes(self):
        return 3 * 1024**3

    @classmethod
    def add_parser_to(clazz, distros):
        arch = distros.add_parser(clazz.DISTRO_KEY, help=clazz.DISTRO_NAME_LONG)
        arch.set_defaults(**{DISTRO_CLASS_FIELD: clazz})

        ArchBootstrapper.add_arguments_to(arch)

    @classmethod
    def create(clazz, messenger, executor, options):
        return clazz(
                messenger,
                executor,
                os.path.abspath(options.cache_dir),
                options.image_date,
                options.mirror_url,
                os.path.abspath(options.resolv_conf),
                )
