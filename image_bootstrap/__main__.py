# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import os
import signal
import sys

from directory_bootstrap.distros.base import \
        add_general_directory_bootstrapping_options
from directory_bootstrap.shared.executor import Executor, sanitize_path
from directory_bootstrap.shared.loaders._argparse import (
        ArgumentParser, RawDescriptionHelpFormatter)
from directory_bootstrap.shared.messenger import (
        BANNER, VERBOSITY_VERBOSE, Messenger, fix_output_encoding)
from directory_bootstrap.shared.metadata import DESCRIPTION, VERSION_STR
from directory_bootstrap.shared.output_control import (
        add_output_control_options, is_color_wanted, run_handle_errors)
from image_bootstrap.distros.arch import ArchStrategy
from image_bootstrap.distros.base import DISTRO_CLASS_FIELD
from image_bootstrap.distros.debian import DebianStrategy
from image_bootstrap.distros.gentoo import GentooStrategy
from image_bootstrap.distros.ubuntu import UbuntuStrategy
from image_bootstrap.engine import (
        BOOTLOADER__AUTO, BOOTLOADER__CHROOT_GRUB2__DEVICE,
        BOOTLOADER__CHROOT_GRUB2__DRIVE, BOOTLOADER__HOST_EXTLINUX,
        BOOTLOADER__HOST_GRUB2__DEVICE, BOOTLOADER__HOST_GRUB2__DRIVE,
        BOOTLOADER__NONE, BootstrapEngine, MachineConfig)
from image_bootstrap.types.disk_id import disk_id_type
from image_bootstrap.types.machine_id import machine_id_type
from image_bootstrap.types.uuid import uuid_type

_BOOTLOADER_APPROACHES = (
        BOOTLOADER__AUTO,
        BOOTLOADER__CHROOT_GRUB2__DEVICE,
        BOOTLOADER__CHROOT_GRUB2__DRIVE,
        BOOTLOADER__HOST_EXTLINUX,
        BOOTLOADER__HOST_GRUB2__DEVICE,
        BOOTLOADER__HOST_GRUB2__DRIVE,
        BOOTLOADER__NONE
        )


def _abspath_or_none(path_or_none):
    return path_or_none and os.path.abspath(path_or_none)


def _main__level_three(messenger, options):
    messenger.banner()

    stdout_wanted = options.verbosity is VERBOSITY_VERBOSE

    if stdout_wanted:
        child_process_stdout = None
    else:
        child_process_stdout = open('/dev/null', 'w')

    sanitize_path()

    executor = Executor(messenger, stdout=child_process_stdout)

    machine_config = MachineConfig(
            options.hostname,
            options.architecture,
            options.root_password,
            _abspath_or_none(options.root_password_file),
            os.path.abspath(options.resolv_conf),
            options.disk_id,
            options.first_partition_uuid,
            options.machine_id,
            options.bootloader_approach,
            options.bootloader_force,
            options.with_openstack,
            )

    bootstrap = BootstrapEngine(
            messenger,
            executor,
            machine_config,
            _abspath_or_none(options.scripts_dir_pre),
            _abspath_or_none(options.scripts_dir_chroot),
            _abspath_or_none(options.scripts_dir_post),
            os.path.abspath(options.target_path),
            options.command_grub2_install,
            )

    distro_class = getattr(options, DISTRO_CLASS_FIELD)
    bootstrap.set_distro(distro_class.create(messenger, executor, options))

    messenger.warn('You are running a version made for (dead) Python 2.'
                   '\n'
                   '         '
                   'Please upgrade to a more recent version made for Python 3.'
                   '\n'
                   '         Thank you!')

    bootstrap.check_release()
    bootstrap.select_bootloader()
    bootstrap.detect_grub2_install()
    bootstrap.check_for_commands()
    bootstrap.check_architecture()
    bootstrap.check_target_block_device()
    bootstrap.check_script_permissions()
    bootstrap.process_root_password()
    bootstrap.run()

    if not stdout_wanted:
        child_process_stdout.close()

    messenger.info('Done.')


def _main__level_two():
    parser = ArgumentParser(
            prog='image-bootstrap',
            description=DESCRIPTION,
            epilog=BANNER,
            formatter_class=RawDescriptionHelpFormatter,
            )
    parser.add_argument('--version', action='version', version=VERSION_STR)

    add_output_control_options(parser)

    machine = parser.add_argument_group('machine configuration')
    machine.add_argument('--arch', dest='architecture', default='amd64',
        help='architecture (e.g. amd64)')
    machine.add_argument('--bootloader', dest='bootloader_approach',
        default=BOOTLOADER__AUTO, choices=_BOOTLOADER_APPROACHES,
        help='approach to take during bootloader installation (default: %(default)s)')
    machine.add_argument('--bootloader-force', default=False, action='store_true',
        help='apply more force when installing bootloader (default: disabled)')
    machine.add_argument('--hostname', default='machine', metavar='NAME',
        help='hostname to set (default: "%(default)s")')
    machine.add_argument('--openstack', dest='with_openstack', default=False, action='store_true',
        help='prepare for use with OpenStack (default: disabled)')
    password_options = machine.add_mutually_exclusive_group()
    password_options.add_argument('--password', dest='root_password', metavar='PASSWORD',
        help='root password to set (default: password log-in disabled)')
    password_options.add_argument('--password-file', dest='root_password_file', metavar='FILE',
        help='file to read root password from (default: password log-in disabled)')
    machine.add_argument('--resolv-conf', metavar='FILE', default='/etc/resolv.conf',
        help='file to copy nameserver entries from (default: %(default)s)')
    machine.add_argument('--disk-id', dest='disk_id', metavar='ID', type=disk_id_type,
        help='specific disk identifier to apply, e.g. 0x12345678')
    machine.add_argument('--first-partition-uuid', dest='first_partition_uuid', metavar='UUID', type=uuid_type,
        help='specific UUID to apply to first partition, e.g. c1b9d5a2-f162-11cf-9ece-0020afc76f16')
    machine.add_argument('--machine-id', dest='machine_id', metavar='ID', type=machine_id_type,
        help='specific machine identifier to apply, e.g. c1b9d5a2f16211cf9ece0020afc76f16')

    script_dirs = parser.add_argument_group('script integration')
    script_dirs.add_argument('--scripts-pre', dest='scripts_dir_pre', metavar='DIRECTORY',
        help='scripts to run prior to chrooting phase, in alphabetical order')
    script_dirs.add_argument('--scripts-chroot', dest='scripts_dir_chroot', metavar='DIRECTORY',
        help='scripts to run during chrooting phase, in alphabetical order')
    script_dirs.add_argument('--scripts-post', dest='scripts_dir_post', metavar='DIRECTORY',
        help='scripts to run after chrooting phase, in alphabetical order')

    commands = parser.add_argument_group('command names')
    commands.add_argument('--grub2-install', metavar='COMMAND', dest='command_grub2_install',
        help='override grub2-install command')

    general = parser.add_argument_group('general configuration')
    add_general_directory_bootstrapping_options(general)

    distros = parser.add_subparsers(title='subcommands (choice of distribution)',
            description='Run "%(prog)s DISTRIBUTION --help" for details '
                    'on options specific to that distribution.',
            metavar='DISTRIBUTION', help='choice of distribution, pick from:')


    for strategy_clazz in (
            ArchStrategy,
            DebianStrategy,
            GentooStrategy,
            UbuntuStrategy,
            ):
        strategy_clazz.add_parser_to(distros)


    parser.add_argument('target_path', metavar='DEVICE',
        help='block device to install to')

    options = parser.parse_args()

    messenger = Messenger(options.verbosity, is_color_wanted(options))
    run_handle_errors(_main__level_three, messenger, options)


def main():
    try:
        fix_output_encoding()
        _main__level_two()
    except KeyboardInterrupt:
        sys.exit(128 + signal.SIGINT)


if __name__ == '__main__':
    main()
