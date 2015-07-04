# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import sys

try:
    from argparse import ArgumentParser, \
            RawDescriptionHelpFormatter
except ImportError:
    print('ERROR: Please use Python >=2.7 or install argparse '
        '(https://pypi.python.org/pypi/argparse).  '
        'Thank you!', file=sys.stderr)
    sys.exit(1)

# Mark as used
ArgumentParser
RawDescriptionHelpFormatter

del sys
