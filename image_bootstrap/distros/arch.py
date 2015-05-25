# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import os


from directory_bootstrap.distros.arch import ArchBootstrapper, \
        SUPPORTED_ARCHITECTURES
from image_bootstrap.distros.base import DISTRO_CLASS_FIELD, DistroStrategy


_COMMAND_CHROOT = 'chroot'


class ArchStrategy(DistroStrategy):
    DISTRO_KEY = 'arch'
    DISTRO_NAME_SHORT = 'Arch'
    DISTRO_NAME_LONG = 'Arch Linux'

    def __init__(self, messenger, executor,
                abs_cache_dir, image_date_triple_or_none, mirror_url):
        self._messenger = messenger
        self._executor = executor

        self._abs_cache_dir = abs_cache_dir
        self._image_date_triple_or_none = image_date_triple_or_none
        self._mirror_url = mirror_url

    def get_commands_to_check_for(self):
        return ArchBootstrapper.get_commands_to_check_for() + [
                _COMMAND_CHROOT,
                ]

    def check_architecture(self, architecture):
        if architecture not in SUPPORTED_ARCHITECTURES:
            raise ValueError('Architecture "%s" not supported' % architecture)

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
                )
        bootstrap.run()

    def create_network_configuration(self, abs_mountpoint):
        pass  # TODO

    def get_chroot_command_grub2_install(self):
        return 'grub-install'

    def generate_grub_cfg_from_inside_chroot(self, abs_mountpoint, env):
        cmd = [
                _COMMAND_CHROOT,
                abs_mountpoint,
                'grub-mkconfig',
                '-o', '/boot/grub/grub.cfg',
                ]
        self._executor.check_call(cmd, env=env)

    def generate_initramfs_from_inside_chroot(self, abs_mountpoint, env):
        pass  # TODO

    def perform_post_chroot_clean_up(self, abs_mountpoint):
        pass  # TODO

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
                options.mirror_url
                )
