# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

from abc import ABCMeta, abstractmethod

from image_bootstrap.engine import \
        BOOTLOADER__CHROOT_GRUB2__DRIVE


DISTRO_CLASS_FIELD = 'distro_class'


class DistroStrategy(object):
    __metaclass__ = ABCMeta

    def __init__(self, messenger, executor, abs_cache_dir, abs_resolv_conf):
        self._messenger = messenger
        self._executor = executor

        self._abs_cache_dir = abs_cache_dir
        self._abs_resolv_conf = abs_resolv_conf

    def check_release(self):
        pass

    def select_bootloader(self):
        return BOOTLOADER__CHROOT_GRUB2__DRIVE

    def write_etc_hostname(self, abs_mountpoint, hostname):
        filename = os.path.join(abs_mountpoint, 'etc', 'hostname')
        self._messenger.info('Writing file "%s"...' % filename)
        f = open(filename, 'w')
        print(self._hostname, file=f)
        f.close()

    @abstractmethod  # leave calling write_etc_hostname to derived classes
    def configure_hostname(self, abs_mountpoint, hostname):
        pass

    @abstractmethod
    def get_commands_to_check_for(self):
        pass

    def check_architecture(self, architecture):
        return architecture

    @abstractmethod
    def allow_autostart_of_services(self, abs_mountpoint, allow):
        pass

    @abstractmethod
    def run_directory_bootstrap(self, abs_mountpoint, architecture, bootloader_approach):
        pass

    @abstractmethod
    def create_network_configuration(self, abs_mountpoint, use_mtu_tristate):
        pass

    @abstractmethod
    def ensure_chroot_has_grub2_installed(self, abs_mountpoint, env):
        pass

    @abstractmethod
    def get_chroot_command_grub2_install(self):
        pass

    @abstractmethod
    def generate_grub_cfg_from_inside_chroot(self, abs_mountpoint, env):
        pass

    def adjust_initramfs_generator_config(self, abs_mountpoint):
        pass

    @abstractmethod
    def generate_initramfs_from_inside_chroot(self, abs_mountpoint, env):
        pass

    @abstractmethod
    def perform_in_chroot_shipping_clean_up(self, abs_mountpoint, env):
        pass

    @abstractmethod
    def perform_post_chroot_clean_up(self, abs_mountpoint):
        pass

    def get_cloud_username(self):
        return self.DISTRO_KEY

    @abstractmethod
    def install_dhcp_client(self, abs_mountpoint, env):
        pass

    @abstractmethod
    def install_sudo(self, abs_mountpoint, env):
        pass

    @abstractmethod
    def install_cloud_init_and_friends(self, abs_mountpoint, env):
        pass

    @abstractmethod
    def get_cloud_init_datasource_cfg_path(self):
        pass

    @abstractmethod
    def install_sshd(self, abs_mountpoint, env):
        pass

    @abstractmethod
    def make_openstack_services_autostart(self, abs_mountpoint, env):
        pass

    @abstractmethod
    def get_vmlinuz_path(self):
        pass

    @abstractmethod
    def get_initramfs_path(self):
        pass

    def prepare_installation_of_packages(self, abs_mountpoint, env):
        pass

    @abstractmethod
    def install_kernel(self, abs_mountpoint, env):
        pass

    @classmethod
    def add_parser_to(clazz, distros):
        raise NotImplementedError()

    @classmethod
    def create(clazz, messenger, executor, options):
        raise NotImplementedError()
