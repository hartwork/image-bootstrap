# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import os
import sys
import subprocess
import traceback
from argparse import ArgumentParser, RawDescriptionHelpFormatter

from directory_bootstrap.shared.executor import Executor
from directory_bootstrap.shared.messenger import Messenger, BANNER, \
        VERBOSITY_QUIET, VERBOSITY_VERBOSE
from directory_bootstrap.shared.metadata import DESCRIPTION, VERSION_STR

from image_bootstrap.engine import \
        BootstrapEngine, \
        BOOTLOADER__AUTO, \
        BOOTLOADER__CHROOT_GRUB2__DEVICE, \
        BOOTLOADER__CHROOT_GRUB2__DRIVE, \
        BOOTLOADER__HOST_GRUB2__DEVICE, \
        BOOTLOADER__HOST_GRUB2__DRIVE, \
        BOOTLOADER__NONE
from image_bootstrap.distros.base import DISTRO_CLASS_FIELD
from image_bootstrap.distros.debian import DebianStrategy
from image_bootstrap.distros.ubuntu import UbuntuStrategy
from image_bootstrap.types.disk_id import disk_id_type
from image_bootstrap.types.uuid import uuid_type


_COLORIZE_NEVER = 'never'
_COLORIZE_ALWAYS = 'always'
_COLORIZE_AUTO = 'auto'

_BOOTLOADER_APPROACHES = (
        BOOTLOADER__AUTO,
        BOOTLOADER__CHROOT_GRUB2__DEVICE,
        BOOTLOADER__CHROOT_GRUB2__DRIVE,
        BOOTLOADER__HOST_GRUB2__DEVICE,
        BOOTLOADER__HOST_GRUB2__DRIVE,
        BOOTLOADER__NONE
        )


def _main__level_three(messenger, options):
    messenger.banner()

    stdout_wanted = options.verbosity is VERBOSITY_VERBOSE

    if stdout_wanted:
        child_process_stdout = None
    else:
        child_process_stdout = open('/dev/null', 'w')

    executor = Executor(messenger, stdout=child_process_stdout)

    bootstrap = BootstrapEngine(
            messenger,
            executor,
            options.hostname,
            options.architecture,
            options.root_password,
            options.root_password_file and os.path.abspath(options.root_password_file),
            os.path.abspath(options.resolv_conf),
            options.disk_id,
            options.first_partition_uuid,
            options.scripts_dir_pre and os.path.abspath(options.scripts_dir_pre),
            options.scripts_dir_chroot and os.path.abspath(options.scripts_dir_chroot),
            options.scripts_dir_post and os.path.abspath(options.scripts_dir_post),
            os.path.abspath(options.target_path),
            options.command_grub2_install,
            options.bootloader_approach,
            options.bootloader_force,
            )

    distro_class = getattr(options, DISTRO_CLASS_FIELD)
    bootstrap.set_distro(distro_class.create(messenger, executor, options))

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
            description=DESCRIPTION,
            epilog=BANNER,
            formatter_class=RawDescriptionHelpFormatter,
            )
    parser.add_argument('--version', action='version', version=VERSION_STR)

    output = parser.add_argument_group('text output configuration')
    output.add_argument('--color', default=_COLORIZE_AUTO, choices=[_COLORIZE_NEVER, _COLORIZE_ALWAYS, _COLORIZE_AUTO],
        help='toggle output color (default: %(default)s)')
    output.add_argument('--debug', action='store_true',
        help='enable debugging')
    output.add_argument('--quiet', dest='verbosity', action='store_const', const=VERBOSITY_QUIET,
        help='limit output to error messages')
    output.add_argument('--verbose', dest='verbosity', action='store_const', const=VERBOSITY_VERBOSE,
        help='increase verbosity')

    machine = parser.add_argument_group('machine configuration')
    machine.add_argument('--arch', dest='architecture', default='amd64',
        help='architecture (e.g. amd64)')
    machine.add_argument('--bootloader', dest='bootloader_approach',
        default=BOOTLOADER__AUTO, choices=_BOOTLOADER_APPROACHES,
        help='approach to take during bootloader installation (default: %(default)s)')
    machine.add_argument('--bootloader-force', default=False, action='store_true',
        help='apply more force when installing bootloader (default: disabled)')
    machine.add_argument('--hostname', required=True, metavar='NAME',
        help='hostname to set')
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

    distros = parser.add_subparsers(title='subcommands (choice of distribution)',
            description='Run "%(prog)s DISTRIBUTION --help" for details '
                    'on options specific to that distribution.',
            metavar='DISTRIBUTION', help='choice of distribution, pick from:')


    for strategy_clazz in (
            DebianStrategy,
            UbuntuStrategy,
            ):
        strategy_clazz.add_parser_to(distros)


    parser.add_argument('target_path', metavar='DEVICE',
        help='block device to install to')

    options = parser.parse_args()

    if options.color == _COLORIZE_AUTO:
        colorize = os.isatty(sys.stdout.fileno())
    else:
        colorize = options.color == _COLORIZE_ALWAYS

    messenger = Messenger(options.verbosity, colorize)
    try:
        _main__level_three(messenger, options)
    except KeyboardInterrupt:
        messenger.info('Interrupted.')
        raise
    except BaseException as e:
        if options.debug:
            traceback.print_exc(file=sys.stderr)

        if isinstance(e, subprocess.CalledProcessError):
            # Manual work to avoid list square brackets in output
            command_flat = ' '.join((messenger.escape_shell(e) for e in e.cmd))
            text = 'Command "%s" returned non-zero exit status %s' % (command_flat, e.returncode)
        else:
            text = str(e)

        messenger.error(text)
        messenger.encourage_bug_reports()
        sys.exit(1)


def main():
    try:
        _main__level_two()
    except KeyboardInterrupt:
        pass
