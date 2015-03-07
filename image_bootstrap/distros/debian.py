# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

from image_bootstrap.distro import BootstrapDistroAgnostic, COMMAND_CHROOT


_COMMAND_DEBOOTSTRAP = 'debootstrap'


class BootstrapDebian(BootstrapDistroAgnostic):
    DISTRO_KEY = 'debian'

    def __init__(self,
            messenger,
            executor,
            hostname,
            architecture,
            root_password,
            debian_release,
            debian_mirror_url,
            abs_scripts_dir_pre,
            abs_scripts_dir_chroot,
            abs_scripts_dir_post,
            abs_target_path,
            ):
        super(BootstrapDebian, self).__init__(
                messenger,
                executor,
                hostname,
                architecture,
                root_password,
                abs_scripts_dir_pre,
                abs_scripts_dir_chroot,
                abs_scripts_dir_post,
                abs_target_path,
                )
        self._release = debian_release
        self._mirror_url = debian_mirror_url

    def get_commands_to_check_for(self):
        return iter(
                list(super(BootstrapDebian, self).get_commands_to_check_for())
                + [
                    COMMAND_CHROOT,
                    _COMMAND_DEBOOTSTRAP,
                ])

    def run_directory_bootstrap(self):
        _extra_packages = (
                'grub2-common',  # for update-grub
                'initramfs-tools',  # for update-initramfs
                'linux-image-%s' % self._architecture,
                )
        cmd = [
                _COMMAND_DEBOOTSTRAP,
                '--arch', self._architecture,
                '--include=%s' % ','.join(_extra_packages),
                self._release,
                self._abs_mountpoint,
                self._mirror_url,
                ]
        self._executor.check_call(cmd)

    def generate_grub_cfg_from_inside_chroot(self):
        cmd = [
                COMMAND_CHROOT,
                self._abs_mountpoint,
                'update-grub',
                ]
        self._executor.check_call(cmd)

    def generate_initramfs_from_inside_chroot(self):
        cmd = [
                COMMAND_CHROOT,
                self._abs_mountpoint,
                'update-initramfs',
                '-u',
                '-k', 'all',
                ]
        self._executor.check_call(cmd)
