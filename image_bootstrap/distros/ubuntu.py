# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import os

from image_bootstrap.distros.debian_based import DebianBasedDistroStrategy
from image_bootstrap.engine import BOOTLOADER__HOST_EXTLINUX


class UbuntuStrategy(DebianBasedDistroStrategy):
    DISTRO_KEY = 'ubuntu'
    DISTRO_NAME_SHORT = 'Ubuntu'
    DISTRO_NAME_LONG = 'Ubuntu'
    DEFAULT_RELEASE = 'trusty'
    DEFAULT_MIRROR_URL = 'http://archive.ubuntu.com/ubuntu'
    APT_CACHER_NG_URL = 'http://localhost:3142/ubuntu'

    def select_bootloader(self):
        return BOOTLOADER__HOST_EXTLINUX

    def check_release(self):
        pass

    def get_kernel_package_name(self, architecture):
        return 'linux-image-generic'

    def _adjust_grub_defaults(self, abs_mountpoint):
        subst = (
            ('GRUB_TIMEOUT=', 'GRUB_TIMEOUT=1'),
            ('GRUB_HIDDEN_TIMEOUT', None),
        )
        etc_default_grub = os.path.join(abs_mountpoint, 'etc/default/grub')
        with open(etc_default_grub, 'r') as f:
            content = f.read()

        lines_to_write = []
        for line in content.split('\n'):
            for prefix, replacement in subst:
                if line.startswith(prefix):
                    if replacement is None:
                        line = '## ' + line
                    else:
                        line = replacement
            lines_to_write.append(line)

        self._messenger.info('Adjusting file "%s"...' % etc_default_grub)
        with open(etc_default_grub, 'w') as f:
            f.write('\n'.join(lines_to_write))

    def generate_grub_cfg_from_inside_chroot(self, abs_mountpoint, env):
        self._adjust_grub_defaults(abs_mountpoint)
        super(UbuntuStrategy, self).generate_grub_cfg_from_inside_chroot(abs_mountpoint, env)

    def install_cloud_init_and_friends(self, abs_mountpoint, env):
        # Do not install cloud-initramfs-growroot (from universe)
        # if cloud-init and growpart alone work just fine
        self._install_packages(['cloud-init', 'cloud-utils'],
                abs_mountpoint, env)
