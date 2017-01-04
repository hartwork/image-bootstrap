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
from directory_bootstrap.shared.commands import COMMAND_FILE, COMMAND_RPM, COMMAND_YUM


_COLLECTIONS_URL = 'https://admin.fedoraproject.org/pkgdb/api/collections/'

_BERKLEY_DB_FORMAT_VERSION_EXTRACTOR = re.compile('^Berkeley DB \\(.*, version (?P<version>[0-9]+),.*\\)$')


def _abs_filename_to_url(abs_filename):
    return 'file://%s' % urllib.pathname2url(abs_filename)


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

    def _check_host_rpm_berkeley_db_version(self, host_rpm_berkeley_db_version):
        chroot_rpm_berkeley_db_version = 9
        if host_rpm_berkeley_db_version > chroot_rpm_berkeley_db_version:
            abs_chroot_rpmdb_path = os.path.join(self._abs_target_dir, 'var/lib/rpm/')
            self._messenger.warn('The future RPM database at %s '
                    '(Berkeley DB file format version %d) '
                    'will not be usable from inside the chroot '
                    'because RPM of Fedora %s supports '
                    'Berkeley DB file format version %d, at most.'
                    % (abs_chroot_rpmdb_path, host_rpm_berkeley_db_version,
                        self._releasever, chroot_rpm_berkeley_db_version)
                    )

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
            self._check_host_rpm_berkeley_db_version(rpm_berkeley_db_version)

            abs_yum_home_dir = os.path.join(abs_temp_dir, 'home')
            os.mkdir(abs_yum_home_dir)

            self._ensure_proper_dbpath(abs_yum_home_dir)

            abs_yum_conf_path = os.path.join(abs_temp_dir, 'yum.conf')
            self._write_yum_conf(abs_yum_conf_path, abs_gpg_public_key_filename)

            self._bootstrap_using_yum(abs_yum_home_dir, abs_yum_conf_path)
        finally:
            self._messenger.info('Cleaning up "%s"...' % abs_temp_dir)
            shutil.rmtree(abs_temp_dir)
