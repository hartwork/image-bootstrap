# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import sys

try:
    from pkg_resources import resource_filename
except ImportError as e:
    print('ERROR: Please install pkg-resources/setuptools '
        '(https://pypi.python.org/pypi/setuptools).  '
        'Thank you!', file=sys.stderr)
    sys.exit(1)

# Mark as used
resource_filename

del sys
