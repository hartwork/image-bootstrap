# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later



import sys

try:
    from requests import get
    from requests.exceptions import HTTPError
except ImportError as e:
    print('ERROR: Please install Requests '
        '(https://pypi.python.org/pypi/requests).  '
        'Thank you!', file=sys.stderr)
    sys.exit(1)

# Create pseudeo-module forwarder
class _ExceptionsModule:
    pass
exceptions = _ExceptionsModule()
exceptions.HTTPError = HTTPError

# Mark as used
get

del sys
