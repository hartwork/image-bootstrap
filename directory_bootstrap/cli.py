# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import argparse
import os
import re
import sys

from directory_bootstrap.distros.arch import ArchBootstrapper, \
        date_argparse_type, SUPPORTED_ARCHITECTURES
from directory_bootstrap.shared.executor import Executor
from directory_bootstrap.shared.messenger import Messenger, \
        VERBOSITY_QUIET, VERBOSITY_VERBOSE
from directory_bootstrap.shared.output_control import \
        add_output_control_options, is_color_wanted, run_handle_errors


def _main__level_three(messenger, options):
    stdout_wanted = options.verbosity is VERBOSITY_VERBOSE

    if stdout_wanted:
        child_process_stdout = None
    else:
        child_process_stdout = open('/dev/null', 'w')

    executor = Executor(messenger, stdout=child_process_stdout)


    bootstrap = ArchBootstrapper(
            messenger,
            executor,
            os.path.abspath(options.target_dir),
            os.path.abspath(options.cache_dir),
            options.architecture,
            options.image_date,
            options.mirror_url,
            os.path.abspath(options.resolv_conf),
            )
    bootstrap.check_for_commands()
    bootstrap.unshare()
    bootstrap.run()


    if not stdout_wanted:
        child_process_stdout.close()


def _main__level_two():
    parser = argparse.ArgumentParser()

    add_output_control_options(parser)

    system = parser.add_argument_group('system configuration')
    system.add_argument('--arch', dest='architecture', default='x86_64',
            choices=SUPPORTED_ARCHITECTURES,
            help='architecture (e.g. x86_64)')
    system.add_argument('--resolv-conf', metavar='FILE', default='/etc/resolv.conf',
        help='file to copy nameserver entries from (default: %(default)s)')

    distros = parser.add_subparsers(title='subcommands (choice of distribution)',
            description='Run "%(prog)s DISTRIBUTION --help" for details '
                    'on options specific to that distribution.',
            metavar='DISTRIBUTION', help='choice of distribution, pick from:')

    arch = distros.add_parser('arch')
    ArchBootstrapper.add_arguments_to(arch)

    parser.add_argument('target_dir', metavar='DIRECTORY')

    options = parser.parse_args()


    messenger = Messenger(options.verbosity, is_color_wanted(options))
    run_handle_errors(_main__level_three, messenger, options)


def main():
    try:
        _main__level_two()
    except KeyboardInterrupt:
        pass
