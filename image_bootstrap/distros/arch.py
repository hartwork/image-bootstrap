# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import os


from directory_bootstrap.distros.arch import ArchBootstrapper, \
        SUPPORTED_ARCHITECTURES
from directory_bootstrap.shared.commands import \
        COMMAND_CHROOT, COMMAND_SED

from image_bootstrap.distros.base import DISTRO_CLASS_FIELD, DistroStrategy


class ArchStrategy(DistroStrategy):
    DISTRO_KEY = 'arch'
    DISTRO_NAME_SHORT = 'Arch'
    DISTRO_NAME_LONG = 'Arch Linux'

    def __init__(self, messenger, executor,
                abs_cache_dir, image_date_triple_or_none, mirror_url,
                abs_resolv_conf):
        self._messenger = messenger
        self._executor = executor

        self._abs_cache_dir = abs_cache_dir
        self._image_date_triple_or_none = image_date_triple_or_none
        self._mirror_url = mirror_url
        self._abs_resolv_conf = abs_resolv_conf

    def get_commands_to_check_for(self):
        return ArchBootstrapper.get_commands_to_check_for() + [
                COMMAND_CHROOT,
                COMMAND_SED,
                ]

    def check_architecture(self, architecture):
        if architecture == 'amd64':
            architecture = 'x86_64'

        if architecture not in SUPPORTED_ARCHITECTURES:
            raise ValueError('Architecture "%s" not supported' % architecture)

        return architecture

    def run_directory_bootstrap(self, abs_mountpoint, architecture, bootloader_approach):
        self._messenger.info('Bootstrapping %s into "%s"...'
                % (self.DISTRO_NAME_SHORT, abs_mountpoint))

        bootstrap = ArchBootstrapper(
                self._messenger,
                self._executor,
                abs_mountpoint,
                self._abs_cache_dir,
                architecture,
                self._image_date_triple_or_none,
                self._mirror_url,
                self._abs_resolv_conf,
                )
        bootstrap.run()

    def create_network_configuration(self, abs_mountpoint):
        pass  # TODO

    def ensure_chroot_has_grub2_installed(self, abs_mountpoint, env):
        cmd = [
                COMMAND_CHROOT,
                abs_mountpoint,
                'pacman',
                '--noconfirm',
                '--sync', 'grub',
                ]
        self._executor.check_call(cmd, env=env)

    def get_chroot_command_grub2_install(self):
        return 'grub-install'

    def generate_grub_cfg_from_inside_chroot(self, abs_mountpoint, env):
        cmd = [
                COMMAND_CHROOT,
                abs_mountpoint,
                'grub-mkconfig',
                '-o', '/boot/grub/grub.cfg',
                ]
        self._executor.check_call(cmd, env=env)

    def adjust_initramfs_generator_config(self, abs_mountpoint):
        abs_linux_preset = os.path.join(abs_mountpoint, 'etc', 'mkinitcpio.d', 'linux.preset')
        self._messenger.info('Adjusting "%s"...' % abs_linux_preset)
        cmd_sed = [
                COMMAND_SED,
                's,^[# \\t]*default_options=.*,default_options="-S autodetect"  # set by image-bootstrap,g',
                '-i', abs_linux_preset,
                ]
        self._executor.check_call(cmd_sed)

    def generate_initramfs_from_inside_chroot(self, abs_mountpoint, env):
        cmd_mkinitcpio = [
                COMMAND_CHROOT,
                abs_mountpoint,
                'mkinitcpio',
                '-p', 'linux',
                ]
        self._executor.check_call(cmd_mkinitcpio, env=env)

    def perform_post_chroot_clean_up(self, abs_mountpoint):
        pass  # TODO

    def install_sudo(self, abs_mountpoint, env):
        raise NotImplementedError()

    def install_cloud_init_and_friends(self, abs_mountpoint, env):
        raise NotImplementedError()

    def get_cloud_init_datasource_cfg_path(self):
        raise NotImplementedError()

    def install_sshd(self, abs_mountpoint, env):
        raise NotImplementedError()

    def make_openstack_services_autostart(self, abs_mountpoint, env):
        raise NotImplementedError()

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
