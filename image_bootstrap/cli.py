# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import os
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter

from image_bootstrap.distros.debian import BootstrapDebian
from image_bootstrap.messenger import Messenger, BANNER
from image_bootstrap.executor import Executor
from image_bootstrap.version import VERSION_STR


_COLORIZE_NEVER = 'never'
_COLORIZE_ALWAYS = 'always'
_COLORIZE_AUTO = 'auto'


def main():
    parser = ArgumentParser(epilog=BANNER, formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('--version', action='version', version=VERSION_STR)

    parser.add_argument('--hostname', required=True, metavar='NAME')
    parser.add_argument('--arch', dest='architecture', default='amd64')
    parser.add_argument('--password', dest='root_password', metavar='PASSWORD')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--quiet', action='store_true')
    parser.add_argument('--color', default=_COLORIZE_AUTO, choices=[_COLORIZE_NEVER, _COLORIZE_ALWAYS, _COLORIZE_AUTO])

    commands = parser.add_argument_group('command names')
    commands.add_argument('--grub2-install', metavar='COMMAND', dest='command_grub2_install', default='grub2-install')

    distros = parser.add_argument_group('choice of distribution')
    distros.add_argument('--debian', dest='distribution', action='store_const', const=BootstrapDebian.DISTRO_KEY, required=True)

    debian = parser.add_argument_group('Debian')
    debian.add_argument('--debian-release', default='wheezy', choices=['wheezy', 'jessie', 'sid'])
    debian.add_argument('--debian-mirror', dest='debian_mirror_url', metavar='URL', default='http://http.debian.net/debian')

    parser.add_argument('--scripts-pre', dest='scripts_dir_pre', metavar='DIRECTORY')
    parser.add_argument('--scripts-chroot', dest='scripts_dir_chroot', metavar='DIRECTORY')
    parser.add_argument('--scripts-post', dest='scripts_dir_post', metavar='DIRECTORY')

    parser.add_argument('target_path', metavar='DEVICE')

    options = parser.parse_args()

    if options.color == _COLORIZE_AUTO:
        colorize = os.isatty(sys.stdout.fileno())
    else:
        colorize = options.color == _COLORIZE_ALWAYS

    messenger = Messenger(bool(options.verbose), colorize)
    messenger.banner()

    if options.quiet:
        child_process_stdout = open('/dev/null', 'w')
    else:
        child_process_stdout = None

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
            )
    bootstrap.check_for_commands()
    bootstrap.run()

    if options.quiet:
        child_process_stdout.close()

    messenger.info('Done.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
