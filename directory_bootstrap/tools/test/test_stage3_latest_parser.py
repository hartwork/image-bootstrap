# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

from textwrap import dedent
from unittest import TestCase

from directory_bootstrap.tools.stage3_latest_parser import \
        find_latest_stage3_date


class TestStag3LatestParser(TestCase):
    def test_(self):
        content = dedent("""\
                # Latest as of Mon, 05 Oct 2015 18:30:01 +0000
                # ts=1444069801
                20151001/stage3-amd64-20151001.tar.bz2 224211865
                20151001/hardened/stage3-amd64-hardened-20151001.tar.bz2 220165244
                20151001/hardened/stage3-amd64-hardened+nomultilib-20151001.tar.bz2 211952954
                20151001/stage3-amd64-nomultilib-20151001.tar.bz2 214753131
                20150905/uclibc/stage3-amd64-uclibc-hardened-20150905.tar.bz2 138274772
                20150905/uclibc/stage3-amd64-uclibc-vanilla-20150905.tar.bz2 135760218
                20150819/stage3-x32-20150819.tar.bz2 241353307
                """)
        (year, month, day), _ = find_latest_stage3_date(content, 'http://distfiles.gentoo.org/releases/amd64/autobuilds/latest-stage3.txt', 'amd64')
        self.assertEquals((year, month, day), (2015, 10, 1))
