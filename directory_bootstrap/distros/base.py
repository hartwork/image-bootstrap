# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import errno
import os
import re
from abc import ABCMeta, abstractmethod
from textwrap import dedent

import directory_bootstrap.shared.loaders._requests as requests
from directory_bootstrap.shared.commands import (
        COMMAND_GPG, COMMAND_WGET, COMMAND_UNSHARE, COMMAND_UNXZ,
        check_for_commands)
from directory_bootstrap.shared.loaders._bs4 import BeautifulSoup
from directory_bootstrap.shared.namespace import unshare_current_process

BOOTSTRAPPER_CLASS_FIELD = 'bootstrapper_class'

_year = '([2-9][0-9]{3})'
_month = '(0[1-9]|1[0-2])'
_day = '(0[1-9]|[12][0-9]|3[01])'

_argparse_date_matcher = re.compile('^%s-%s-%s$' % (_year, _month, _day))

_GPG_DISPLAY_KEY_FORMAT = '0xlong'


def date_argparse_type(text):
    m = _argparse_date_matcher.match(text)
    if m is None:
        raise ValueError('Not a well-formed date: "%s"' % text)
    return tuple((int(m.group(i)) for i in range(1, 3 + 1)))

date_argparse_type.__name__ = 'date'


def add_general_directory_bootstrapping_options(general):
    general.add_argument('--cache-dir', metavar='DIRECTORY',
            default='/var/cache/directory-bootstrap/',
            help='directory to use for downloads (default: %(default)s)')


class DirectoryBootstrapper(object):
    __metaclass__ = ABCMeta

    def __init__(self, messenger, executor, abs_target_dir, abs_cache_dir):
        self._messenger = messenger
        self._executor = executor
        self._abs_target_dir = abs_target_dir
        self._abs_cache_dir = abs_cache_dir

    @abstractmethod
    def wants_to_be_unshared(self):
        pass

    @classmethod
    def add_parser_to(clazz, distros):
        distro = distros.add_parser(clazz.DISTRO_KEY, help=clazz.DISTRO_NAME_LONG)
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
        soup = BeautifulSoup(listing_html, 'lxml')
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

    def uncompress_xz_tarball(self, tarball_filename):
        extension = '.xz'

        if not tarball_filename.endswith(extension):
            raise ValueError('Filename "%s" does not end with "%s"' % (tarball_filename, extension))

        uncompressed_tarball_filename = tarball_filename[:-len(extension)]

        if os.path.exists(uncompressed_tarball_filename):
            self._messenger.info('Re-using cache file "%s".' % uncompressed_tarball_filename)
        else:
            self._messenger.info('Uncompressing file "%s"...' % tarball_filename)
            self._executor.check_call([
                    COMMAND_UNXZ,
                    '--keep',
                    tarball_filename,
                    ])

            if not os.path.exists(uncompressed_tarball_filename):
                raise OSError(errno.ENOENT, 'File "%s" does not exists' % uncompressed_tarball_filename)

        return uncompressed_tarball_filename

    def _ensure_directory_writable(self, abs_path, creation_mode):
        try:
            os.makedirs(abs_path, creation_mode)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

            self._messenger.info('Checking access to "%s"...' % abs_path)
            if not os.path.exists(abs_path):
                raise IOError(errno.ENOENT, 'No such file or directory: \'%s\'' % abs_path)

            if not os.access(os.path.join(abs_path, ''), os.W_OK):
                raise IOError(errno.EACCES, 'Permission denied: \'%s\'' % abs_path)
        else:
            # NOTE: Sounding like future is intentional.
            self._messenger.info('Creating directory "%s"...' % abs_path)

    def ensure_directories_writable(self):
        self._ensure_directory_writable(self._abs_cache_dir, 0755)
        self._ensure_directory_writable(self._abs_target_dir, 0700)

    @staticmethod
    def _abs_keyserver_cert_filename(abs_gpg_home_dir):
        return os.path.join(abs_gpg_home_dir, 'sks-keyservers.netCA.pem')

    def _initialize_gpg_home(self, abs_temp_dir):
        abs_gpg_home_dir = os.path.join(abs_temp_dir, 'gpg_home')
        self._messenger.info('Initializing temporary GnuPG home at "%s"...' % abs_gpg_home_dir)
        os.mkdir(abs_gpg_home_dir, 0700)

        self.download_url_to_file(
            # This one was trouble: https://sks-keyservers.net/sks-keyservers.netCA.pem
            'https://raw.githubusercontent.com/gpg/gnupg/master/dirmngr/sks-keyservers.netCA.pem',
            self._abs_keyserver_cert_filename(abs_gpg_home_dir))

        with open(os.path.join(abs_gpg_home_dir, 'dirmngr.conf'), 'w') as f:
            print(dedent("""\
                keyserver hkps://hkps.pool.sks-keyservers.net
                hkp-cacert %s
            """ % self._abs_keyserver_cert_filename(abs_gpg_home_dir)), file=f)

        return abs_gpg_home_dir

    def _get_gpg_argv_start(self, abs_gpg_home_dir):
        return [
                COMMAND_UNSHARE,
                '--fork', '--pid',  # to auto-kill started gpg-agent
                COMMAND_GPG,
                '--home', abs_gpg_home_dir,
                '--keyid-format', _GPG_DISPLAY_KEY_FORMAT,
                '--batch',
            ]

    def _import_gpg_key_file(self, abs_gpg_home_dir, abs_key_path):
        self._messenger.info('Importing GPG key from file "{}"...'.format(abs_key_path))
        cmd = self._get_gpg_argv_start(abs_gpg_home_dir) + [
                '--quiet',
                '--import', abs_key_path,
            ]
        self._executor.check_call(cmd)

    def _verify_file_gpg(self, candidate_filename, signature_filename, abs_gpg_home_dir):
        self._messenger.info('Verifying integrity of file "%s"...' % candidate_filename)
        cmd = self._get_gpg_argv_start(abs_gpg_home_dir) + [
                '--verify',
                signature_filename,
                candidate_filename,
            ]
        self._executor.check_call(cmd)
