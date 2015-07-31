# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import sys

try:
    from yaml import dump, load
except ImportError:
    print('ERROR: Please install PyYAML '
        '(https://pypi.python.org/pypi/PyYAML).  '
        'Thank you!', file=sys.stderr)
    sys.exit(1)

# Mark as used
dump
load

del sys
