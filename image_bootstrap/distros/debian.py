# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

from image_bootstrap.distros.debian_based import DebianBasedDistroStrategy


class DebianStrategy(DebianBasedDistroStrategy):
    DISTRO_KEY = 'debian'
    DISTRO_NAME_SHORT = 'Debian'
    DISTRO_NAME_LONG = 'Debian GNU/Linux'
    DEFAULT_RELEASE = 'jessie'
    DEFAULT_MIRROR_URL = 'http://httpredir.debian.org/debian'
    APT_CACHER_NG_URL = 'http://localhost:3142/debian'

    def check_release(self):
        if self._release in ('stable', 'testing'):
            raise ValueError('For Debian releases, please use names like "jessie" rather than "%s".'
                % self._release)

    def get_kernel_package_name(self, architecture):
        if architecture == 'i386':
            return 'linux-image-686-pae'

        return 'linux-image-%s' % architecture

    def install_cloud_init_and_friends(self, abs_mountpoint, env):
        self._install_packages(['cloud-init', 'cloud-utils', 'cloud-initramfs-growroot'],
                abs_mountpoint, env)
