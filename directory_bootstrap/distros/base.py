# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import os

from abc import ABCMeta, abstractmethod

from directory_bootstrap.shared.commands import check_for_commands, COMMAND_WGET
from directory_bootstrap.shared.namespace import unshare_current_process


BOOTSTRAPPER_CLASS_FIELD = 'bootstrapper_class'


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

    @abstractmethod
    def run(self):
        pass

    @classmethod
    def add_arguments_to(clazz, distro):
        raise NotImplementedError()

    @classmethod
    def create(clazz, messenger, executor, options):
        raise NotImplementedError()

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
