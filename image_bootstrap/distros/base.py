# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from abc import ABCMeta, abstractmethod

from image_bootstrap.engine import \
        COMMAND_CHROOT, \
        BOOTLOADER__CHROOT_GRUB2__DRIVE


DISTRO_CLASS_FIELD = 'distro_class'


class DistroStrategy(object):
    __metaclass__ = ABCMeta

    def check_release(self):
        pass

    def select_bootloader(self):
        return BOOTLOADER__CHROOT_GRUB2__DRIVE

    @abstractmethod
    def get_commands_to_check_for(self):
        pass

    def check_architecture(self, architecture):
        pass

    @abstractmethod
    def run_directory_bootstrap(self, abs_mountpoint, architecture, bootloader_approach):
        pass

    @abstractmethod
    def create_network_configuration(self, abs_mountpoint):
        pass

    @abstractmethod
    def get_chroot_command_grub2_install(self):
        pass

    @abstractmethod
    def generate_grub_cfg_from_inside_chroot(self, abs_mountpoint, env):
        pass

    @abstractmethod
    def generate_initramfs_from_inside_chroot(self, abs_mountpoint, env):
        pass

    @abstractmethod
    def perform_post_chroot_clean_up(self, abs_mountpoint):
        pass

    @classmethod
    def add_parser_to(clazz, distros):
        raise NotImplementedError()

    @classmethod
    def create(clazz, messenger, executor, options):
        raise NotImplementedError()
