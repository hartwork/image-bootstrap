# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import re

_DISK_ID_PATTERN = '^0x[0-9a-fA-F]{1,8}$'
_DISK_ID_MATCHER = re.compile(_DISK_ID_PATTERN)


def _hex_string_to_number(text):
    if not _DISK_ID_MATCHER.match(text):
        raise ValueError('"%s" does not match pattern "%s"' % (text, _DISK_ID_PATTERN))

    return int(text, 16)


class DiskIdentifier(object):
    def __init__(self, number):
        self._number = number

    def __str__(self):
        return '0x%8x' % self._number

    def byte_sequence(self):
        return ''.join([chr((self._number >> i * 8) & 255) for i in range(4)])


def disk_id_type(text):
    """
    Meant to be used as an argparse type
    """
    return DiskIdentifier(_hex_string_to_number(text))


disk_id_type.__name__ = 'disk identifier'
