# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import re

_MACHINE_ID_PATTERN = '^[0-9a-f]{32}$'
_MACHINE_ID_MATCHER = re.compile(_MACHINE_ID_PATTERN)


def machine_id_type(text):
    """
    Meant to be used as an argparse type
    """
    if not _MACHINE_ID_MATCHER.match(text):
        raise ValueError('"%s" does not match pattern "%s"' % (text, _MACHINE_ID_PATTERN))
    return text


machine_id_type.__name__ = 'machine identifier'
