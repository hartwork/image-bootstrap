# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later



from image_bootstrap.distros.debian_based import DebianBasedDistroStrategy


class DebianStrategy(DebianBasedDistroStrategy):
    DISTRO_KEY = 'debian'
    DISTRO_NAME_SHORT = 'Debian'
    DISTRO_NAME_LONG = 'Debian GNU/Linux'
    DEFAULT_RELEASE = 'trixie'
    DEFAULT_MIRROR_URL = 'http://httpredir.debian.org/debian'
    APT_CACHER_NG_URL = 'http://localhost:3142/debian'

    def check_release(self):
        if self._release in ('oldoldstable', 'oldstable', 'stable', 'testing'):
            raise ValueError('For Debian releases, please use names like "%s" rather than "%s".'
                % (self.DEFAULT_RELEASE, self._release))

        if self._release in ('wheezy', 'jessie', 'stretch', 'buster', 'bullseye'):
            raise ValueError('Release "%s" is no longer supported.' % self._release)

    def get_kernel_package_name(self, architecture):
        if architecture == 'i386':
            return 'linux-image-686-pae'

        return 'linux-image-%s' % architecture

    def install_cloud_init_and_friends(self):
        self._install_packages(['cloud-init', 'cloud-utils', 'cloud-initramfs-growroot'])

    def uses_systemd(self):
        return True

    def uses_systemd_resolved(self, with_openstack):
        return False

    def get_minimum_size_bytes(self):
        return 2 * 1024**3

    def get_extra_mkfs_ext4_options(self):
        args = super(DebianStrategy, self).get_extra_mkfs_ext4_options()
        args += ['-O', '^metadata_csum']
        return args
