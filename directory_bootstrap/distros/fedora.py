# Copyright (C) 2016 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import json
import os
import shutil
import tempfile

from textwrap import dedent

from directory_bootstrap.distros.base import DirectoryBootstrapper
from directory_bootstrap.shared.commands import COMMAND_YUM


_COLLECTIONS_URL = 'https://admin.fedoraproject.org/pkgdb/api/collections/'


class FedoraBootstrapper(DirectoryBootstrapper):
    DISTRO_KEY = 'fedora'
    DISTRO_NAME_LONG = 'Fedora'

    def __init__(self, messenger, executor, abs_target_dir, abs_cache_dir, releasever):
        super(FedoraBootstrapper, self).__init__(
                messenger,
                executor,
                abs_target_dir,
                abs_cache_dir,
                )
        self._releasever = releasever

    def wants_to_be_unshared(self):
        return True

    @staticmethod
    def get_commands_to_check_for():
        return DirectoryBootstrapper.get_commands_to_check_for() + [
                COMMAND_YUM,
                ]

    @classmethod
    def add_arguments_to(clazz, distro):
        distro.add_argument('--release', metavar='VERSION',
                help='release to bootstrap (e.g. 24)')

    @classmethod
    def create(clazz, messenger, executor, options):
        return clazz(
                messenger,
                executor,
                os.path.abspath(options.target_dir),
                os.path.abspath(options.cache_dir),
                options.release,
                )

    def _bootstrap_using_yum(self, abs_yum_home_dir, abs_yum_conf_path):
        env = os.environ.copy()
        env['HOME'] = abs_yum_home_dir

        argv = [
            COMMAND_YUM,
            '--assumeyes',
            '--config', abs_yum_conf_path,
            '--installroot', self._abs_target_dir,
            '--releasever', str(self._releasever),
            'install', '@core',
        ]
        self._executor.check_call(argv, env)

    def _ensure_proper_dbpath(self, abs_yum_home_dir):
        """
        Debian patches rpm's dbpath default to something other than
        /var/lib/rpm, so we bypass that change to have "rpm -qa" work
        as expected in the resulting chroot.
        """
        with open(os.path.join(abs_yum_home_dir, '.rpmmacros'), 'w') as f:
            print('%_dbpath /var/lib/rpm', file=f)

    def _write_yum_conf(self, abs_yum_conf_path):
        with open(abs_yum_conf_path, 'w') as f:
            # TODO Use key of release X, current key is release 24
            print(dedent("""\
                    [fedora]
                    name=Fedora $releasever - $basearch
                    failovermethod=priority
                    metalink=https://mirrors.fedoraproject.org/metalink?repo=fedora-$releasever&arch=$basearch
                    enabled=1
                    metadata_expire=7d
                    gpgcheck=1
                    gpgkey=https://getfedora.org/static/81B46521.txt
                    skip_if_unavailable=False
                    """), file=f)

    def _find_latest_release(self):
        json_content = self.get_url_content(_COLLECTIONS_URL)
        try:
            content = json.loads(json_content)
            return sorted([
                    int(c['version']) for c in content['collections']
                    if c['name'] == 'Fedora' and c['version'].isdigit()
            ])[-1]
        except:
            raise ValueError(
                    'Could not extract latest release from %s content' \
                    % _COLLECTIONS_URL)

    def run(self):
        self.ensure_directories_writable()

        if self._releasever is None:
            self._messenger.info('Searching for latest release...')
            self._releasever = self._find_latest_release()
            self._messenger.info('Found %d to be latest.' % self._releasever)

        abs_temp_dir = os.path.abspath(tempfile.mkdtemp())
        try:
            abs_yum_home_dir = os.path.join(abs_temp_dir, 'home')
            os.mkdir(abs_yum_home_dir)

            self._ensure_proper_dbpath(abs_yum_home_dir)

            abs_yum_conf_path = os.path.join(abs_temp_dir, 'yum.conf')
            self._write_yum_conf(abs_yum_conf_path)

            self._bootstrap_using_yum(abs_yum_home_dir, abs_yum_conf_path)
        finally:
            self._messenger.info('Cleaning up "%s"...' % abs_temp_dir)
            shutil.rmtree(abs_temp_dir)
