# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later



import sys

try:
    from colorama import Fore, Style
except ImportError:
    print('ERROR: Please install Colorama '
        '(https://pypi.python.org/pypi/colorama).  '
        'Thank you!', file=sys.stderr)
    sys.exit(1)

# Mark as used
Fore
Style

del sys
