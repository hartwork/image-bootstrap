# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import argparse
import os
import re
import sys

from directory_bootstrap.distros.arch import ArchBootstrapper, date_argparse_type

from image_bootstrap.messenger import Messenger, \
        VERBOSITY_QUIET, VERBOSITY_VERBOSE
from image_bootstrap.executor import Executor


_COLORIZE_NEVER = 'never'
_COLORIZE_ALWAYS = 'always'
_COLORIZE_AUTO = 'auto'


def main():
    parser = argparse.ArgumentParser()

    output = parser.add_argument_group('text output configuration')
    output.add_argument('--color', default=_COLORIZE_AUTO, choices=[_COLORIZE_NEVER, _COLORIZE_ALWAYS, _COLORIZE_AUTO],
        help='toggle output color (default: %(default)s)')
    output.add_argument('--debug', action='store_true',
        help='enable debugging')
    output.add_argument('--quiet', dest='verbosity', action='store_const', const=VERBOSITY_QUIET,
        help='limit output to error messages')
    output.add_argument('--verbose', dest='verbosity', action='store_const', const=VERBOSITY_VERBOSE,
        help='increase verbosity')


    distros = parser.add_subparsers(title='subcommands (choice of distribution)',
            description='Run "%(prog)s DISTRIBUTION --help" for details '
                    'on options specific to that distribution.',
            metavar='DISTRIBUTION', help='choice of distribution, pick from:')

    arch = distros.add_parser('arch')

    arch.add_argument('--arch', default='x86_64')
    arch.add_argument('--image-date', type=date_argparse_type)
    arch.add_argument('--cache-dir', default='/var/cache/dir-bootstrap/')
    arch.add_argument('--mirror', dest='mirror_url', metavar='URL', default='http://mirror.rackspace.com/archlinux/$repo/os/$arch')

    parser.add_argument('target_dir', metavar='DIRECTORY')

    options = parser.parse_args()


    if options.color == _COLORIZE_AUTO:
        colorize = os.isatty(sys.stdout.fileno())
    else:
        colorize = options.color == _COLORIZE_ALWAYS

    messenger = Messenger(options.verbosity, colorize)


    stdout_wanted = options.verbosity is VERBOSITY_VERBOSE

    if stdout_wanted:
        child_process_stdout = None
    else:
        child_process_stdout = open('/dev/null', 'w')

    executor = Executor(messenger, stdout=child_process_stdout)


    options.cache_dir = os.path.abspath(options.cache_dir)
    options.target_dir = os.path.abspath(options.target_dir)

    boostrap = ArchBootstrapper(
            messenger,
            executor,
            options.target_dir,
            options.cache_dir,
            options.arch,
            options.image_date,
            options.mirror_url,
            )
    boostrap.run()


    if not stdout_wanted:
        child_process_stdout.close()
