# Copyright (C) 2016 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import json
import os
import re
import shutil
import tempfile
import urllib

from textwrap import dedent

from directory_bootstrap.distros.base import DirectoryBootstrapper
from directory_bootstrap.shared.commands import (COMMAND_CHROOT,
        COMMAND_FILE, COMMAND_RPM, COMMAND_YUM, EXIT_COMMAND_NOT_FOUND, find_command)


_COLLECTIONS_URL = 'https://admin.fedoraproject.org/pkgdb/api/collections/'

_BERKLEY_DB_FORMAT_VERSION_EXTRACTOR = re.compile('^Berkeley DB \\(.*, version (?P<version>[0-9]+),.*\\)$')

_DB_HASH_VERSION_SUPPORTED_AT_MOST_IN = {
    6: [(3, 0)],
    7: [
        (3, 1), (3, 2), (3, 3),
        (4, 0), (4, 1), (4, 2), (4, 3), (4, 4), (4, 5),
    ],
    8: [],
    9: [
        (4, 6), (4, 7), (4, 8), (4, 9),
        (5, 0), (5, 1), (5, 2), (5, 3),
    ],
    10: [
        (6, 0), (6, 1), (6, 2),
    ],
}


def _abs_filename_to_url(abs_filename):
    return 'file://%s' % urllib.pathname2url(abs_filename)


def _get_db_dump_command_names(hash_version):
    """
    >>> _get_db_dump_command_names(10)
    ['db6.2_dump', 'db6.1_dump', 'db6.0_dump', 'db_dump']
    """

    res = []
    for k, v in sorted(_DB_HASH_VERSION_SUPPORTED_AT_MOST_IN.items()):
        if k >= hash_version:
            for major_minor in reversed(v):
                res.append('db%d.%d_dump' % major_minor)
    res.append('db_dump')
    return res


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
                COMMAND_CHROOT,
                COMMAND_FILE,
                COMMAND_RPM,
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
        self._messenger.info('Bootstrapping %s into "%s" using yum...'
                % (self.DISTRO_NAME_LONG, self._abs_target_dir))

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
        abs_rpmmacros_path = os.path.join(abs_yum_home_dir, '.rpmmacros')
        self._messenger.info('Writing file "%s"...' % abs_rpmmacros_path)
        with open(abs_rpmmacros_path, 'w') as f:
            print('%_dbpath /var/lib/rpm', file=f)

    def _write_yum_conf(self, abs_yum_conf_path, abs_gpg_public_key_filename):
        self._messenger.info('Writing file "%s"...' % abs_yum_conf_path)
        gpg_public_key_file_url = _abs_filename_to_url(abs_gpg_public_key_filename)
        with open(abs_yum_conf_path, 'w') as f:
            print(dedent("""\
                    [fedora]
                    name=Fedora $releasever - $basearch
                    failovermethod=priority
                    metalink=https://mirrors.fedoraproject.org/metalink?repo=fedora-$releasever&arch=$basearch
                    enabled=1
                    metadata_expire=7d
                    gpgcheck=1
                    gpgkey=%s
                    skip_if_unavailable=False

                    [updates]
                    name=Fedora $releasever - $basearch - Updates
                    failovermethod=priority
                    metalink=https://mirrors.fedoraproject.org/metalink?repo=updates-released-f$releasever&arch=$basearch
                    enabled=1
                    metadata_expire=6h
                    gpgcheck=1
                    gpgkey=%s
                    skip_if_unavailable=False

                    [updates-testing]
                    name=Fedora $releasever - $basearch - Test Updates
                    failovermethod=priority
                    metalink=https://mirrors.fedoraproject.org/metalink?repo=updates-testing-f$releasever&arch=$basearch
                    enabled=1
                    metadata_expire=6h
                    gpgcheck=1
                    gpgkey=%s
                    skip_if_unavailable=False
                    """ % (gpg_public_key_file_url, gpg_public_key_file_url, gpg_public_key_file_url)), file=f)

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

    def _download_fedora_release_public_key(self):
        self._messenger.info('Downloading related GnuPG public key...')
        rel_gpg_public_key_filename = 'RPM-GPG-KEY-fedora-%s-primary' \
                % self._releasever
        abs_gpg_public_key_filename = os.path.join(self._abs_cache_dir, rel_gpg_public_key_filename)
        self.download_url_to_file(
                'https://pagure.io/fedora-repos/raw/master/f/%s' % rel_gpg_public_key_filename,
                abs_gpg_public_key_filename)
        return abs_gpg_public_key_filename

    def _determine_host_rpm_berkeley_db_version(self, abs_temp_dir):
        self._messenger.info('Checking compatibility of Berkeley DB versions...')
        db_root = os.path.join(abs_temp_dir, 'dbtest')
        self._executor.check_call([
                COMMAND_RPM,
                '--initdb',
                '--root', db_root,
                '--dbpath', '',
                ])
        file_command_output = self._executor.check_output([
                COMMAND_FILE,
                '--brief',
                os.path.join(db_root, 'Packages'),
                ])
        m = _BERKLEY_DB_FORMAT_VERSION_EXTRACTOR.match(file_command_output)
        return int(m.group('version'))

    def _repair_var_lib_rpm(self, rpm_berkeley_db_version):
        self._messenger.info('Repairing RPM package database...')
        for db_dump_command in _get_db_dump_command_names(rpm_berkeley_db_version):
            try:
                abs_path_db_dump = find_command(db_dump_command)
                self._messenger.info('Checking for %s... %s' % (db_dump_command, abs_path_db_dump))
                break
            except OSError:
                self._messenger.info('Checking for %s... not found' % db_dump_command)
                pass
        else:
            raise OSError(EXIT_COMMAND_NOT_FOUND, 'No db*_dump command found in PATH.')

        abs_path_packages = '/var/lib/rpm/Packages'
        abs_full_path_packages = os.path.join(self._abs_target_dir, abs_path_packages.lstrip('/'))

        fd, abs_full_path_temp = tempfile.mkstemp(
                prefix='Packages-',
                suffix='.dump',
                dir=os.path.dirname(abs_full_path_packages))
        try:
            os.close(fd)

            abs_path_temp = os.path.join(
                    os.path.dirname(abs_path_packages),
                    os.path.split(abs_full_path_temp)[-1])

            # Export
            self._executor.check_call([
                    abs_path_db_dump,
                    '-f', abs_full_path_temp,
                    abs_full_path_packages,
                    ])

            os.remove(abs_full_path_packages)

            # Import
            self._executor.check_call([
                    COMMAND_CHROOT,
                    self._abs_target_dir,
                    'db_load',
                    '-f', abs_path_temp,
                    abs_path_packages,
                    ])
        finally:
            os.remove(abs_full_path_temp)

    def run(self):
        self.ensure_directories_writable()

        if self._releasever is None:
            self._messenger.info('Searching for latest release...')
            self._releasever = str(self._find_latest_release())
            self._messenger.info('Found %s to be latest.' % self._releasever)

        abs_gpg_public_key_filename = self._download_fedora_release_public_key()

        abs_temp_dir = os.path.abspath(tempfile.mkdtemp())
        try:
            rpm_berkeley_db_version = self._determine_host_rpm_berkeley_db_version(abs_temp_dir)

            abs_yum_home_dir = os.path.join(abs_temp_dir, 'home')
            os.mkdir(abs_yum_home_dir)

            self._ensure_proper_dbpath(abs_yum_home_dir)

            abs_yum_conf_path = os.path.join(abs_temp_dir, 'yum.conf')
            self._write_yum_conf(abs_yum_conf_path, abs_gpg_public_key_filename)

            self._bootstrap_using_yum(abs_yum_home_dir, abs_yum_conf_path)

            self._repair_var_lib_rpm(rpm_berkeley_db_version)
        finally:
            self._messenger.info('Cleaning up "%s"...' % abs_temp_dir)
            shutil.rmtree(abs_temp_dir)
