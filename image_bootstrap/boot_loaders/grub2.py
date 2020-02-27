# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later



import errno
import os

from directory_bootstrap.shared.commands import COMMAND_CHROOT

BOOTLOADER__CHROOT_GRUB2__DEVICE = 'chroot-grub2-device'
BOOTLOADER__CHROOT_GRUB2__DRIVE = 'chroot-grub2-drive'
BOOTLOADER__HOST_GRUB2__DEVICE = 'host-grub2-device'
BOOTLOADER__HOST_GRUB2__DRIVE = 'host-grub2-drive'

BOOTLOADER__CHROOT_GRUB2 = (
        BOOTLOADER__CHROOT_GRUB2__DEVICE,
        BOOTLOADER__CHROOT_GRUB2__DRIVE,
        )

_BOOTLOADER__ANY_GRUB2__DRIVE = (
        BOOTLOADER__CHROOT_GRUB2__DRIVE,
        BOOTLOADER__HOST_GRUB2__DRIVE,
        )


class GrubTwoInstaller(object):
    def __init__(self,
            messenger,
            executor,
            abs_target_path,
            bootloader_approach,
            bootloader_force,
            command_host_grub2_install,
            command_chroot_grub2_install,
            chroot_env,
            abs_mountpoint,
            ):
        self._messenger = messenger
        self._executor = executor

        self._abs_target_path = abs_target_path
        self._bootloader_approach = bootloader_approach
        self._bootloader_force = bootloader_force

        self._command_host_grub2_install = command_host_grub2_install

        self._command_chroot_grub2_install = command_chroot_grub2_install
        self._chroot_env = chroot_env
        self._abs_mountpoint = abs_mountpoint

    def _create_bootloader_install_message(self, real_abs_target):
        hints = []
        if real_abs_target != os.path.normpath(self._abs_target_path):
            hints.append('actually "%s"' % real_abs_target)
        hints.append('approach "%s"' % self._bootloader_approach)

        return 'Installing bootloader to device "%s" (%s)...' % (
                self._abs_target_path, ', '.join(hints))

    def run(self):
        real_abs_target = os.path.realpath(self._abs_target_path)
        message = self._create_bootloader_install_message(real_abs_target)

        use_chroot = self._bootloader_approach in BOOTLOADER__CHROOT_GRUB2
        use_device_map = self._bootloader_approach in _BOOTLOADER__ANY_GRUB2__DRIVE

        chroot_boot_grub = os.path.join(self._abs_mountpoint, 'boot', 'grub')
        try:
            os.makedirs(chroot_boot_grub, 0o755)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        if use_device_map:
            # Write device map just for being able to call grub-install
            abs_chroot_device_map = os.path.join(chroot_boot_grub, 'device.map')
            grub_drive = '(hd9999)'
            self._messenger.info('Writing device map to "%s" (mapping "%s" to "%s")...' \
                    % (abs_chroot_device_map, grub_drive, real_abs_target))
            f = open(abs_chroot_device_map, 'w')
            print('%s\t%s' % (grub_drive, real_abs_target), file=f)
            f.close()

        self._messenger.info(message)

        cmd = []

        if use_chroot:
            cmd += [
                COMMAND_CHROOT,
                self._abs_mountpoint,
                self._command_chroot_grub2_install,
                ]
            env = self._chroot_env
        else:
            cmd += [
                self._command_host_grub2_install,
                '--boot-directory',
                os.path.join(self._abs_mountpoint, 'boot'),
                ]
            env = None

        cmd.append('--target=i386-pc')  # ensure non-EFI

        if self._bootloader_force:
            cmd.append('--force')

        if use_device_map:
            cmd.append(grub_drive)
        else:
            cmd.append(self._abs_target_path)

        self._executor.check_call(cmd, env=env)

        if use_device_map:
            os.remove(abs_chroot_device_map)
