# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import argparse
import os
import re
import sys

from directory_bootstrap.distros.arch import ArchBootstrapper, date_argparse_type
from directory_bootstrap.shared.executor import Executor
from directory_bootstrap.shared.messenger import Messenger, \
        VERBOSITY_QUIET, VERBOSITY_VERBOSE
from directory_bootstrap.shared.output_control import \
        add_output_control_options, is_color_wanted


def _main__level_three(messenger, options):
    stdout_wanted = options.verbosity is VERBOSITY_VERBOSE

    if stdout_wanted:
        child_process_stdout = None
    else:
        child_process_stdout = open('/dev/null', 'w')

    executor = Executor(messenger, stdout=child_process_stdout)


    options.cache_dir = os.path.abspath(options.cache_dir)
    options.target_dir = os.path.abspath(options.target_dir)

    bootstrap = ArchBootstrapper(
            messenger,
            executor,
            options.target_dir,
            options.cache_dir,
            options.arch,
            options.image_date,
            options.mirror_url,
            )
    bootstrap.run()


    if not stdout_wanted:
        child_process_stdout.close()


def _main__level_two():
    parser = argparse.ArgumentParser()

    add_output_control_options(parser)

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


    messenger = Messenger(options.verbosity, is_color_wanted(options))

    _main__level_three(messenger, options)


def main():
    try:
        _main__level_two()
    except KeyboardInterrupt:
        pass
