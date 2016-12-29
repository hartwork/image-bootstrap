# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

from unittest import TestCase

from directory_bootstrap.shared.byte_size import format_byte_size


class TestByteSizeFormatter(TestCase):
    def test_some(self):
        for size_bytes, expected in (
                (0, '0 byte'),
                (1, '1 byte'),
                (2, '2 byte'),
                (511, '511 byte'),
                (512, '0.5 KiB'),
                (513, '0.501 KiB'),
                (1023, '0.999 KiB'),
                (1024, '1 KiB'),
                (1025, '1.001 KiB'),
                (1024 * 1024 - 1, '1 MiB'),
                (1024 * 1024, '1 MiB'),
                (1024 * 1024 + 1, '1 MiB'),
                (1024**3, '1 GiB'),
                (1024**4, '1 TiB'),
                ):
            received = format_byte_size(size_bytes)
            self.assertEquals(received, expected)
