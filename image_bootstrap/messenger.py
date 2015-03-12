# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import re
import sys

from image_bootstrap.version import VERSION_STR, RELEASE_DATE_STR


_NEEDS_ESCAPING = re.compile('([!`"\'$ \\\\{}()?*&<>;])')

_IMAGE_BOOSTRAP_PREFIX = 'ib| '


BANNER = """\
     _                          __             __      __               
    (_)_ _  ___ ____ ____  ___ / /  ___  ___  / /____ / /________ ____  
   / /  ' \/ _ `/ _ `/ -_)/__// _ \/ _ \/ _ \/ __(_-</ __/ __/ _ `/ _ \ 
  /_/_/_/_/\_,_/\_, /\__/    /_.__/\___/\___/\__/___/\__/_/  \_,_/ .__/ 
               /___/                    %(3456789_123456789_)s  /_/     

Software libre licensed under AGPL v3 or later.
Brought to you by Sebastian Pipping <sebastian@pipping.org>.
Please report bugs at https://github.com/hartwork/image-bootstrap.  Thank you!\
""" % {
    '3456789_123456789_': '%*s' \
        % (len('%(3456789_123456789_)s'),
        'v%s :: %s' % (VERSION_STR, RELEASE_DATE_STR))
    }


class Messenger(object):
    def __init__(self, verbose):
        self._verbose = verbose

    def banner(self):
        if not self._verbose:
            return

        print(BANNER)
        print()

    def escape_shell(self, text):
        return _NEEDS_ESCAPING.sub('\\\\\\1', text)

    def announce_command(self, argv):
        if not self._verbose:
            return
        print(_IMAGE_BOOSTRAP_PREFIX + '# %s' % ' '.join((self.escape_shell(e) for e in argv)))

    def info(self, text):
        if not self._verbose:
            return
        print(_IMAGE_BOOSTRAP_PREFIX + text)

    def error(self, text):
        print(_IMAGE_BOOSTRAP_PREFIX + text, file=sys.stderr)
