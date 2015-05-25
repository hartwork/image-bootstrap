# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import os
import sys
import traceback

from directory_bootstrap.shared.messenger import VERBOSITY_QUIET, VERBOSITY_VERBOSE


_COLORIZE_NEVER = 'never'
_COLORIZE_ALWAYS = 'always'
_COLORIZE_AUTO = 'auto'


def add_output_control_options(parser):
    output = parser.add_argument_group('text output configuration')
    output.add_argument('--color', default=_COLORIZE_AUTO, choices=[_COLORIZE_NEVER, _COLORIZE_ALWAYS, _COLORIZE_AUTO],
        help='toggle output color (default: %(default)s)')
    output.add_argument('--debug', action='store_true',
        help='enable debugging')
    output.add_argument('--quiet', dest='verbosity', action='store_const', const=VERBOSITY_QUIET,
        help='limit output to error messages')
    output.add_argument('--verbose', dest='verbosity', action='store_const', const=VERBOSITY_VERBOSE,
        help='increase verbosity')


def is_color_wanted(options):
    if options.color == _COLORIZE_AUTO:
        colorize = os.isatty(sys.stdout.fileno())
    else:
        colorize = options.color == _COLORIZE_ALWAYS

    return colorize
