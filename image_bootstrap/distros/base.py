# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import os
from abc import ABCMeta, abstractmethod

import image_bootstrap.loaders._yaml as yaml
from directory_bootstrap.shared.commands import COMMAND_WGET
from image_bootstrap.engine import BOOTLOADER__CHROOT_GRUB2__DRIVE

DISTRO_CLASS_FIELD = 'distro_class'


class DistroStrategy(object):
    __metaclass__ = ABCMeta

    def __init__(self, messenger, executor, abs_cache_dir, abs_resolv_conf):
        self._messenger = messenger
        self._executor = executor

        self._abs_cache_dir = abs_cache_dir
        self._abs_resolv_conf = abs_resolv_conf

    def set_mountpoint(self, abs_mountpoint):
        self._abs_mountpoint = abs_mountpoint

    def set_chroot_env_prototype(self, chroot_env_prototype):
        self._chroot_env_prototype = chroot_env_prototype

    def create_chroot_env(self):
        return self._chroot_env_prototype.copy()

    def check_release(self):
        pass

    def select_bootloader(self):
        return BOOTLOADER__CHROOT_GRUB2__DRIVE

    def write_etc_hostname(self, hostname):
        filename = os.path.join(self._abs_mountpoint, 'etc', 'hostname')
        self._messenger.info('Writing file "%s"...' % filename)
        f = open(filename, 'w')
        print(hostname, file=f)
        f.close()

    @abstractmethod  # leave calling write_etc_hostname to derived classes
    def configure_hostname(self, hostname):
        pass

    @abstractmethod
    def get_commands_to_check_for(self):
        pass

    def check_architecture(self, architecture):
        return architecture

    @abstractmethod
    def allow_autostart_of_services(self, allow):
        pass

    @abstractmethod
    def run_directory_bootstrap(self, architecture, bootloader_approach):
        pass

    @abstractmethod
    def create_network_configuration(self, use_mtu_tristate):
        pass

    @abstractmethod
    def ensure_chroot_has_grub2_installed(self):
        pass

    @abstractmethod
    def get_chroot_command_grub2_install(self):
        pass

    @abstractmethod
    def generate_grub_cfg_from_inside_chroot(self):
        pass

    def adjust_initramfs_generator_config(self):
        pass

    @abstractmethod
    def generate_initramfs_from_inside_chroot(self):
        pass

    @abstractmethod
    def perform_in_chroot_shipping_clean_up(self):
        pass

    @abstractmethod
    def perform_post_chroot_clean_up(self):
        pass

    def get_cloud_username(self):
        return self.DISTRO_KEY

    def get_cloud_init_distro(self):
        return self.DISTRO_KEY

    @abstractmethod
    def install_dhcp_client(self):
        pass

    @abstractmethod
    def install_sudo(self):
        pass

    @abstractmethod
    def install_cloud_init_and_friends(self):
        pass

    @abstractmethod
    def get_cloud_init_datasource_cfg_path(self):
        pass

    @abstractmethod
    def install_sshd(self):
        pass

    @abstractmethod
    def make_openstack_services_autostart(self):
        pass

    @abstractmethod
    def get_vmlinuz_path(self):
        pass

    @abstractmethod
    def get_initramfs_path(self):
        pass

    def prepare_installation_of_packages(self):
        pass

    @abstractmethod
    def install_kernel(self):
        pass

    def _fetch_install_chmod(self, url, local_path, permissions):
        full_local_path = os.path.join(self._abs_mountpoint, local_path.lstrip('/'))
        cmd = [
                COMMAND_WGET,
                '-O%s' % full_local_path,
                url,
                ]
        self._executor.check_call(cmd)
        os.chmod(full_local_path, permissions)

    def install_growpart(self):
        self._messenger.info('Fetching growpart of cloud-utils...')
        self._fetch_install_chmod(
                'https://git.launchpad.net/cloud-utils/plain/bin/growpart?id=75cdc65ea3586a08975f662a263d766cf2dc6d6f',
                '/usr/bin/growpart', 0755)

    def disable_cloud_init_syslog_fix_perms(self):
        # https://github.com/hartwork/image-bootstrap/issues/17
        filename = os.path.join(self._abs_mountpoint, 'etc/cloud/cloud.cfg.d/00_syslog_fix_perms.cfg')
        self._messenger.info('Writing file "%s"...' % filename)
        with open(filename, 'w') as f:
            print('syslog_fix_perms: null', file=f)

    def adjust_cloud_cfg_dict(self, cloud_cfg_dict):
        system_info = cloud_cfg_dict.setdefault('system_info', {})

        system_info__default_user = system_info.setdefault('default_user', {})
        system_info__default_user['name'] = self.get_cloud_username()
        system_info__default_user['gecos'] = 'Cloud-init-user'
        system_info__default_user.setdefault('sudo',
                                             ['ALL=(ALL) NOPASSWD:ALL'])

        system_info['distro'] = self.get_cloud_init_distro()

    def adjust_etc_cloud_cfg(self):
        filename = os.path.join(self._abs_mountpoint, 'etc/cloud/cloud.cfg')
        self._messenger.info('Adjusting file "%s"...' % filename)
        with open(filename, 'r') as f:
            d = yaml.load(f.read())
        self.adjust_cloud_cfg_dict(d)
        with open(filename, 'w') as f:
            print('# Re-written by image-bootstrap', file=f)
            print(yaml.dump(d, default_flow_style=False), file=f)

    @abstractmethod
    def uses_systemd(self):
        pass

    @abstractmethod
    def uses_systemd_resolved(self, with_openstack):
        pass

    @abstractmethod
    def get_minimum_size_bytes(self):
        pass

    def adjust_grub_defaults(self, with_openstack):
        pass

    def install_acpid(self):
        # NOTE: Only called for distros NOT using systemd
        raise NotImplementedError()

    def get_extra_mkfs_ext4_options(self):
        return []

    @classmethod
    def add_parser_to(clazz, distros):
        raise NotImplementedError()

    @classmethod
    def create(clazz, messenger, executor, options):
        raise NotImplementedError()
