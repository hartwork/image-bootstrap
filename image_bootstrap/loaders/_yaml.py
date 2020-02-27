# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later



import sys

try:
    from yaml import safe_dump, safe_load
except ImportError:
    print('ERROR: Please install PyYAML '
        '(https://pypi.python.org/pypi/PyYAML).  '
        'Thank you!', file=sys.stderr)
    sys.exit(1)

# Mark as used
safe_dump
safe_load

del sys
