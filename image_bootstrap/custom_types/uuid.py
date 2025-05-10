# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import re

_UUID_PATTERN = '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
_SANE_UUID_CHECKER = re.compile(_UUID_PATTERN)


def require_valid_uuid(text):
    if not _SANE_UUID_CHECKER.match(text):
        raise ValueError('Not a well-formed UUID: "%s"' % text)


def uuid_type(text):
    """
    Meant to be used as an argparse type
    """
    require_valid_uuid(text)
    return text


uuid_type.__name__ = 'UUID'
