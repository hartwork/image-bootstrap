# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import sys

try:
    from bs4 import BeautifulSoup
except ImportError:
    print('ERROR: Please install Beautiful Soup '
        '(https://pypi.python.org/pypi/beautifulsoup4).  '
        'Thank you!', file=sys.stderr)
    sys.exit(1)

# Mark as used
BeautifulSoup

del sys
