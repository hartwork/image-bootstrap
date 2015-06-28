# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from image_bootstrap.distros.debian import DebianStrategy


class UbuntuStrategy(DebianStrategy):
    DISTRO_KEY = 'ubuntu'
    DISTRO_NAME_SHORT = 'Ubuntu'
    DISTRO_NAME_LONG = 'Ubuntu'
    DEFAULT_RELEASE = 'trusty'
    DEFAULT_MIRROR_URL = 'http://archive.ubuntu.com/ubuntu'
    APT_CACHER_NG_URL = 'http://localhost:3142/ubuntu'

    def get_kernel_package_name(self, architecture):
        return 'linux-image-generic'

    def install_cloud_init_and_friends(self, abs_mountpoint, env):
        # Do not install cloud-initramfs-growroot (from universe)
        # if cloud-init and growpart alone work just fine
        self._install_packages(['cloud-init', 'cloud-utils'],
                abs_mountpoint, env)
