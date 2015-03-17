# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import os
import sys
import subprocess
import traceback
from argparse import ArgumentParser, RawDescriptionHelpFormatter

from image_bootstrap.distros.debian import BootstrapDebian
from image_bootstrap.messenger import Messenger, BANNER
from image_bootstrap.executor import Executor
from image_bootstrap.metadata import DESCRIPTION, VERSION_STR


_COLORIZE_NEVER = 'never'
_COLORIZE_ALWAYS = 'always'
_COLORIZE_AUTO = 'auto'

_VERBOSITY_QUIET = object()
_VERBOSITY_VERBOSE = object()


def _main__level_three(messenger, options):
    messenger.banner()

    stdout_wanted = options.verbosity is _VERBOSITY_VERBOSE

    if stdout_wanted:
        child_process_stdout = None
    else:
        child_process_stdout = open('/dev/null', 'w')

    executor = Executor(messenger, stdout=child_process_stdout)

    bootstrap = BootstrapDebian(
            messenger,
            executor,
            options.hostname,
            options.architecture,
            options.root_password,
            options.debian_release,
            options.debian_mirror_url,
            options.scripts_dir_pre and os.path.abspath(options.scripts_dir_pre),
            options.scripts_dir_chroot and os.path.abspath(options.scripts_dir_chroot),
            options.scripts_dir_post and os.path.abspath(options.scripts_dir_post),
            os.path.abspath(options.target_path),
            options.command_grub2_install,
            options.command_debootstrap,
            )
    bootstrap.check_for_commands()
    bootstrap.check_script_executability()
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
    output.add_argument('--quiet', dest='verbosity', action='store_const', const=_VERBOSITY_QUIET,
        help='limit output to error messages')
    output.add_argument('--verbose', dest='verbosity', action='store_const', const=_VERBOSITY_VERBOSE,
        help='increase verbosity')

    machine = parser.add_argument_group('machine configuration')
    machine.add_argument('--arch', dest='architecture', default='amd64',
        help='architecture (e.g. amd64)')
    machine.add_argument('--hostname', required=True, metavar='NAME',
        help='hostname to set')
    machine.add_argument('--password', dest='root_password', metavar='PASSWORD',
        help='root password to set (default: none / password log-in disabled)')

    script_dirs = parser.add_argument_group('script integration')
    script_dirs.add_argument('--scripts-pre', dest='scripts_dir_pre', metavar='DIRECTORY',
        help='scripts to run prior to chrooting phase, in alphabetical order')
    script_dirs.add_argument('--scripts-chroot', dest='scripts_dir_chroot', metavar='DIRECTORY',
        help='scripts to run during chrooting phase, in alphabetical order')
    script_dirs.add_argument('--scripts-post', dest='scripts_dir_post', metavar='DIRECTORY',
        help='scripts to run after chrooting phase, in alphabetical order')

    distros = parser.add_argument_group('choice of distribution')
    distros.add_argument('--debian', dest='distribution', action='store_const', const=BootstrapDebian.DISTRO_KEY, required=True,
        help='select Debian for a distribution')

    commands = parser.add_argument_group('command names')
    commands.add_argument('--debootstrap', metavar='COMMAND', dest='command_debootstrap', default='debootstrap',
        help='override debootstrap command')
    commands.add_argument('--grub2-install', metavar='COMMAND', dest='command_grub2_install', default='grub2-install',
        help='override grub2-install command')


    debian = parser.add_argument_group('Debian')
    debian.add_argument('--debian-release', default='wheezy', choices=['wheezy', 'jessie', 'sid'],
        help='specify Debian release')
    debian.add_argument('--debian-mirror', dest='debian_mirror_url', metavar='URL', default='http://http.debian.net/debian',
        help='specify Debian mirror to use')


    parser.add_argument('target_path', metavar='DEVICE',
        help='block device to install to')

    options = parser.parse_args()

    if options.color == _COLORIZE_AUTO:
        colorize = os.isatty(sys.stdout.fileno())
    else:
        colorize = options.color == _COLORIZE_ALWAYS

    messages_wanted = options.verbosity is not _VERBOSITY_QUIET

    messenger = Messenger(messages_wanted, colorize)
    try:
        _main__level_three(messenger, options)
    except KeyboardInterrupt:
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
