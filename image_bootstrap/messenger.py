# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import re
import sys


_NEEDS_ESCAPING = re.compile('([!`"\'$ \\\\])')


class Messenger(object):
    def __init__(self, verbose):
        self._verbose = verbose

    def escape_shell(self, text):
        return _NEEDS_ESCAPING.sub('\\\\\\1', text)

    def announce_command(self, argv):
        if not self._verbose:
            return
        print('# %s' % ' '.join((self.escape_shell(e) for e in argv)))

    def info(self, text):
        if not self._verbose:
            return
        print(text)

    def error(self, text):
        print(text, file=sys.stderr)
