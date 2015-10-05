# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

_UNIT_LABELS = (
    'byte',
    'KiB',
    'MiB',
    'GiB',
    'TiB',
)


def format_byte_size(size_bytes):
    FACTOR = 1024
    for exponent, unit in enumerate(_UNIT_LABELS):
        if size_bytes < FACTOR:
            if size_bytes < FACTOR / 2:
                final_unit = unit
            else:
                final_unit = _UNIT_LABELS[exponent + 1]
                size_bytes /= float(FACTOR)

            value = str('%.3f' % size_bytes).rstrip('0').rstrip('.')
            return '%s %s' % (value, final_unit)

        size_bytes /= float(FACTOR)
    else:
        raise ValueError('Byte size too large to be supported')
