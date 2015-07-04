# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import os
import re

from abc import ABCMeta, abstractmethod

import directory_bootstrap.shared.loaders._requests as requests

from directory_bootstrap.shared.loaders._bs4 import BeautifulSoup

from directory_bootstrap.shared.commands import check_for_commands, COMMAND_WGET
from directory_bootstrap.shared.namespace import unshare_current_process


BOOTSTRAPPER_CLASS_FIELD = 'bootstrapper_class'

_year = '([2-9][0-9]{3})'
_month = '(0[1-9]|1[12])'
_day = '(0[1-9]|[12][0-9]|3[01])'

_argparse_date_matcher = re.compile('^%s-%s-%s$' % (_year, _month, _day))


def date_argparse_type(text):
    m = _argparse_date_matcher.match(text)
    if m is None:
        raise ValueError('Not a well-formed date: "%s"' % text)
    return tuple((int(m.group(i)) for i in range(1, 3 + 1)))

date_argparse_type.__name__ = 'date'


class DirectoryBootstrapper(object):
    __metaclass__ = ABCMeta

    @classmethod
    def add_parser_to(clazz, distros):
        distro = distros.add_parser(clazz.DISTRO_KEY)
        distro.set_defaults(**{BOOTSTRAPPER_CLASS_FIELD: clazz})
        clazz.add_arguments_to(distro)

    def check_for_commands(self):
        check_for_commands(self._messenger, self.get_commands_to_check_for())

    @staticmethod
    def get_commands_to_check_for():
        return [
                COMMAND_WGET,
                ]

    def unshare(self):
        unshare_current_process(self._messenger)

    def extract_latest_date(self, listing_html, date_matcher):
        soup = BeautifulSoup(listing_html)
        dates = []
        for link in soup.find_all('a'):
            m = date_matcher.search(link.get('href'))
            if not m:
                continue
            dates.append(m.group(0))

        return sorted(dates)[-1]

    @abstractmethod
    def run(self):
        pass

    @classmethod
    def add_arguments_to(clazz, distro):
        raise NotImplementedError()

    @classmethod
    def create(clazz, messenger, executor, options):
        raise NotImplementedError()

    def get_url_content(self, url):
        return requests.get(url).text

    def download_url_to_file(self, url, filename):
        if os.path.exists(filename):
            self._messenger.info('Re-using cache file "%s".' % filename)
            return

        self._messenger.info('Downloading "%s"...' % url)
        cmd = [
                COMMAND_WGET,
                '-O%s' % filename,
                url,
                ]
        self._executor.check_call(cmd)
