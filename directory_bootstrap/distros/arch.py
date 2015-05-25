# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import errno
import os
import re
import requests
import shutil
import subprocess
import tempfile

from bs4 import BeautifulSoup
from tarfile import TarFile


_GPG_DISPLAY_KEY_FORMAT = '0xlong'

_NON_DISK_MOUNT_TASKS = (
        ('/dev', ['-o', 'bind'], 'dev'),
        ('/dev/pts', ['-o', 'bind'], 'dev/pts'),
        ('/dev/shm', ['-o', 'bind'], 'dev/shm'),
        )

_COMMAND_CHROOT = 'chroot'
_COMMAND_GPG = 'gpg'
_COMMAND_WGET = 'wget'
_COMMAND_MOUNT = 'mount'
_COMMAND_UMOUNT = 'umount'


_year = '([2-9][0-9]{3})'
_month = '(0[1-9]|1[12])'
_day = '(0[1-9]|[12][0-9]|3[01])'

_keyring_package_date_matcher = re.compile('%s%s%s' % (_year, _month, _day))
_image_date_matcher = re.compile('%s\\.%s\\.%s' % (_year, _month, _day))
_argparse_date_matcher = re.compile('^%s-%s-%s$' % (_year, _month, _day))


def date_argparse_type(text):
    m = _argparse_date_matcher.match(text)
    if m is None:
        raise ValueError('Not a well-formed date: "%s"' % text)
    return tuple((int(m.group(i)) for i in range(1, 3 + 1)))

date_argparse_type.__name__ = 'date'


class ArchBootstrapper(object):
    def __init__(self, messenger, executor, abs_target_dir, abs_cache_dir, architecture, image_date_triple_or_none):
        self._messenger = messenger
        self._executor = executor
        self._abs_target_dir = abs_target_dir
        self._abs_cache_dir = abs_cache_dir
        self._architecture = architecture
        self._image_date_triple_or_none = image_date_triple_or_none

    def _get_keyring_listing(self):
        self._messenger.info('Downloading keyring listing...')
        r = requests.get('https://sources.archlinux.org/other/archlinux-keyring/')    
        return r.text

    def _get_image_listing(self):
        self._messenger.info('Downloading image listing...')
        r = requests.get('https://mirrors.kernel.org/archlinux/iso/')    
        return r.text

    def _extract_latest_date(self, listing_html, date_matcher):
        soup = BeautifulSoup(listing_html)
        dates = []
        for link in soup.find_all('a'):
            m = date_matcher.search(link.get('href'))
            if not m:
                continue
            dates.append(m.group(0))

        return sorted(dates)[-1]

    def _download_url_to_file(self, url, filename):
        if os.path.exists(filename):
            self._messenger.info('Re-using cache file "%s".' % filename)
            return

        self._messenger.info('Downloading "%s"...' % url)
        cmd = [
                _COMMAND_WGET,
                '-O%s' % filename,
                url,
                ]
        self._executor.check_call(cmd)

    def _download_keyring_package(self, package_yyyymmdd, suffix=''):
        filename = os.path.join(self._abs_cache_dir, 'archlinux-keyring-%s.tar.gz%s' % (package_yyyymmdd, suffix))
        url = 'https://sources.archlinux.org/other/archlinux-keyring/archlinux-keyring-%s.tar.gz%s' % (package_yyyymmdd, suffix)
        self._download_url_to_file(url, filename)
        return filename

    def _download_image(self, image_yyyy_mm_dd, suffix=''):
        filename = os.path.join(self._abs_cache_dir, 'archlinux-bootstrap-%s-%s.tar.gz%s' % (image_yyyy_mm_dd, self._architecture, suffix))
        url = 'https://mirrors.kernel.org/archlinux/iso/%s/archlinux-bootstrap-%s-%s.tar.gz%s' % (image_yyyy_mm_dd, image_yyyy_mm_dd, self._architecture, suffix)
        self._download_url_to_file(url, filename)
        return filename

    def _initialize_gpg_home(self, abs_temp_dir, package_filename, package_yyyymmdd):
        abs_gpg_home_dir = os.path.join(abs_temp_dir, 'gpg_home')
        self._messenger.info('Initializing temporary GnuPG home at "%s"...' % abs_gpg_home_dir)
        os.mkdir(abs_gpg_home_dir, 0700)

        rel_archlinux_gpg_path = 'archlinux-keyring-%s/archlinux.gpg' % package_yyyymmdd
        with TarFile.open(package_filename) as tf:
            tf.extract(rel_archlinux_gpg_path, path=abs_temp_dir)
        abs_archlinux_gpg_path = os.path.join(abs_temp_dir, rel_archlinux_gpg_path)

        cmd = [
                _COMMAND_GPG,
                '--home', abs_gpg_home_dir,
                '--keyid-format', _GPG_DISPLAY_KEY_FORMAT,
                '--no-autostart',
                '--batch',

                '--quiet',
                '--import', abs_archlinux_gpg_path,
            ]
        self._executor.check_call(cmd)

        return abs_gpg_home_dir

    def _verify_file_gpg(self, candidate_filename, signature_filename, abs_gpg_home_dir):
        self._messenger.info('Verifying integrity of file "%s"...' % candidate_filename)
        cmd = [
                _COMMAND_GPG,
                '--home', abs_gpg_home_dir,
                '--keyid-format', _GPG_DISPLAY_KEY_FORMAT,
                '--no-autostart',
                '--batch',

                '--verify',
                signature_filename,
                candidate_filename,
            ]
        self._executor.check_call(cmd)

    def _require_cache_writable(self):
        self._messenger.info('Checking access to "%s"...' % self._abs_cache_dir)
        if not os.path.exists(self._abs_cache_dir):
            raise IOError(errno.ENOENT, 'No such file or directory: \'%s\'' % self._abs_cache_dir)

        if not os.access(os.path.join(self._abs_cache_dir, ''), os.W_OK):
            raise IOError(errno.EACCES, 'Permission denied: \'%s\'' % self._abs_cache_dir)

    def _extract_image(self, image_filename, abs_temp_dir):
        abs_pacstrap_outer_root = os.path.join(abs_temp_dir, 'pacstrap_root', '')

        self._messenger.info('Extracting bootstrap image to "%s"...' % abs_pacstrap_outer_root)
        abs_pacstrap_inner_root = os.path.join(abs_pacstrap_outer_root, 'root.%s' % self._architecture)
        with TarFile.open(image_filename) as tf:
            tf.extractall(path=abs_pacstrap_outer_root)

        return abs_pacstrap_inner_root

    def _make_chroot_env(self):
        env = os.environ.copy()
        for key in ('LANG', 'LANGUAGE'):
            env.pop(key, None)
        env.update({
                'LC_ALL': 'C',
                })
        return env

    def _prepare_pacstrap(self, abs_pacstrap_inner_root):
        self._messenger.info('Initializing pacman keyring...')

        env = self._make_chroot_env()

        cmd = [
                _COMMAND_CHROOT,
                abs_pacstrap_inner_root,
                'unshare', '--fork', '--pid',  # to auto-kill started gpg-agent
                'pacman-key',
                '--init',
                ]
        self._executor.check_call(cmd, env=env)

        cmd = [
                _COMMAND_CHROOT,
                abs_pacstrap_inner_root,
                'unshare', '--fork', '--pid',  # to auto-kill started gpg-agent
                'pacman-key',
                '--populate', 'archlinux',
                ]
        self._executor.check_call(cmd, env=env)

    def run(self):
        self._require_cache_writable()

        try:
            os.makedirs(self._abs_target_dir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        abs_temp_dir = os.path.abspath(tempfile.mkdtemp())
        try:
            if self._image_date_triple_or_none is None:
                image_listing_html = self._get_image_listing()
                image_yyyy_mm_dd = self._extract_latest_date(image_listing_html, _image_date_matcher)
            else:
                image_yyyy_mm_dd = '%04s.%02d.%02d' % self._image_date_triple_or_none

            keyring_listing_html = self._get_keyring_listing()
            package_yyyymmdd = self._extract_latest_date(keyring_listing_html, _keyring_package_date_matcher)

            package_sig_filename = self._download_keyring_package(package_yyyymmdd, '.sig')
            package_filename = self._download_keyring_package(package_yyyymmdd)

            abs_gpg_home_dir = self._initialize_gpg_home(abs_temp_dir, package_filename, package_yyyymmdd)
            self._verify_file_gpg(package_filename, package_sig_filename, abs_gpg_home_dir)

            image_sig_filename = self._download_image(image_yyyy_mm_dd, '.sig')
            image_filename = self._download_image(image_yyyy_mm_dd)
            self._verify_file_gpg(image_filename, image_sig_filename, abs_gpg_home_dir)


            abs_pacstrap_inner_root = self._extract_image(image_filename, abs_temp_dir)


            rel_pacstrap_target_dir = os.path.join('mnt', 'arch_root', '')
            abs_pacstrap_target_dir = os.path.join(abs_pacstrap_inner_root, rel_pacstrap_target_dir)

            os.makedirs(abs_pacstrap_target_dir)

            self._executor.check_call([
                    _COMMAND_MOUNT,
                    '-o', 'bind',
                    self._abs_target_dir,
                    abs_pacstrap_target_dir,
                    ])
            try:
                for source, options, target in _NON_DISK_MOUNT_TASKS:
                    self._executor.check_call([
                            _COMMAND_MOUNT,
                            source,
                            ] \
                            + options \
                            + [
                                os.path.join(abs_pacstrap_inner_root, target),
                            ])

                try:
                    self._prepare_pacstrap(abs_pacstrap_inner_root)
                finally:
                    for source, options, target in reversed(_NON_DISK_MOUNT_TASKS):
                        abs_path = os.path.join(abs_pacstrap_inner_root, target)
                        self._executor.check_call([
                                _COMMAND_UMOUNT,
                                abs_path,
                                ])

            finally:
                self._executor.check_call([
                        _COMMAND_UMOUNT,
                        abs_pacstrap_target_dir,
                        ])

        finally:
            self._messenger.info('Cleaning up "%s"...' % abs_temp_dir)
            shutil.rmtree(abs_temp_dir)
