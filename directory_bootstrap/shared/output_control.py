# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import os
import subprocess
import sys
import traceback

from directory_bootstrap.shared.messenger import (
        VERBOSITY_QUIET, VERBOSITY_VERBOSE)

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


def run_handle_errors(main_function, messenger, options):
    try:
        main_function(messenger, options)
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
        elif hasattr(e, '_ib_abs_script_filename'):
            text = '%s (script "%s")' % (str(e), e._ib_abs_script_filename)
        else:
            text = str(e)

        messenger.error(text)
        messenger.encourage_bug_reports()
        sys.exit(1)
