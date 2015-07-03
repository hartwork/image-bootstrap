# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import datetime
import errno
import os
import re
import shutil
import subprocess
import sys
import tempfile

from tarfile import TarFile

import directory_bootstrap.shared.loaders._requests as requests

from directory_bootstrap.distros.base import DirectoryBootstrapper
from directory_bootstrap.shared.commands import \
        COMMAND_CHROOT, COMMAND_GPG, COMMAND_MOUNT, \
        COMMAND_UMOUNT, COMMAND_UNSHARE
from directory_bootstrap.shared.loaders._bs4 import BeautifulSoup
from directory_bootstrap.shared.mount import try_unmounting
from directory_bootstrap.shared.resolv_conf import filter_copy_resolv_conf


SUPPORTED_ARCHITECTURES = ('i686', 'x86_64')

_GPG_DISPLAY_KEY_FORMAT = '0xlong'

_NON_DISK_MOUNT_TASKS = (
        ('/dev', ['-o', 'bind'], 'dev'),
        ('/dev/pts', ['-o', 'bind'], 'dev/pts'),  # for gpgme
        ('PROC', ['-t', 'proc'], 'proc'),  # for pacstrap mountpoint detection
        )


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


class ArchBootstrapper(DirectoryBootstrapper):
    DISTRO_KEY = 'arch'

    def __init__(self, messenger, executor, abs_target_dir, abs_cache_dir,
                architecture, image_date_triple_or_none, mirror_url,
                abs_resolv_conf):
        self._messenger = messenger
        self._executor = executor
        self._abs_target_dir = abs_target_dir
        self._abs_cache_dir = abs_cache_dir
        self._architecture = architecture
        self._image_date_triple_or_none = image_date_triple_or_none
        self._mirror_url = mirror_url
        self._abs_resolv_conf = abs_resolv_conf

    @staticmethod
    def get_commands_to_check_for():
        return DirectoryBootstrapper.get_commands_to_check_for() + [
                COMMAND_CHROOT,
                COMMAND_GPG,
                COMMAND_MOUNT,
                COMMAND_UMOUNT,
                ]

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

    def _download_keyring_package(self, package_yyyymmdd, suffix=''):
        filename = os.path.join(self._abs_cache_dir, 'archlinux-keyring-%s.tar.gz%s' % (package_yyyymmdd, suffix))
        url = 'https://sources.archlinux.org/other/archlinux-keyring/archlinux-keyring-%s.tar.gz%s' % (package_yyyymmdd, suffix)
        self.download_url_to_file(url, filename)
        return filename

    def _download_image(self, image_yyyy_mm_dd, suffix=''):
        filename = os.path.join(self._abs_cache_dir, 'archlinux-bootstrap-%s-%s.tar.gz%s' % (image_yyyy_mm_dd, self._architecture, suffix))
        url = 'https://mirrors.kernel.org/archlinux/iso/%s/archlinux-bootstrap-%s-%s.tar.gz%s' % (image_yyyy_mm_dd, image_yyyy_mm_dd, self._architecture, suffix)
        self.download_url_to_file(url, filename)
        return filename

    def _get_gpg_argv_start(self, abs_gpg_home_dir):
        return [
                COMMAND_UNSHARE,
                '--fork', '--pid',  # to auto-kill started gpg-agent
                COMMAND_GPG,
                '--home', abs_gpg_home_dir,
                '--keyid-format', _GPG_DISPLAY_KEY_FORMAT,
                '--batch',
            ]

    def _initialize_gpg_home(self, abs_temp_dir, package_filename, package_yyyymmdd):
        abs_gpg_home_dir = os.path.join(abs_temp_dir, 'gpg_home')
        self._messenger.info('Initializing temporary GnuPG home at "%s"...' % abs_gpg_home_dir)
        os.mkdir(abs_gpg_home_dir, 0700)

        rel_archlinux_gpg_path = 'archlinux-keyring-%s/archlinux.gpg' % package_yyyymmdd
        with TarFile.open(package_filename) as tf:
            tf.extract(rel_archlinux_gpg_path, path=abs_temp_dir)
        abs_archlinux_gpg_path = os.path.join(abs_temp_dir, rel_archlinux_gpg_path)

        cmd = self._get_gpg_argv_start(abs_gpg_home_dir) + [
                '--quiet',
                '--import', abs_archlinux_gpg_path,
            ]
        self._executor.check_call(cmd)

        return abs_gpg_home_dir

    def _verify_file_gpg(self, candidate_filename, signature_filename, abs_gpg_home_dir):
        self._messenger.info('Verifying integrity of file "%s"...' % candidate_filename)
        cmd = self._get_gpg_argv_start(abs_gpg_home_dir) + [
                '--verify',
                signature_filename,
                candidate_filename,
            ]
        self._executor.check_call(cmd)

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

    def _adjust_pacman_mirror_list(self, abs_pacstrap_inner_root):
        abs_mirrorlist = os.path.join(abs_pacstrap_inner_root, 'etc/pacman.d/mirrorlist')
        self._messenger.info('Adjusting mirror list at "%s"...' % abs_mirrorlist)
        with open(abs_mirrorlist, 'a') as f:
            print(file=f)
            print('## Added by directory-bootstrap', file=f)
            print('Server = %s' % self._mirror_url, file=f)

    def _copy_etc_resolv_conf(self, abs_pacstrap_inner_root):
        target = os.path.join(abs_pacstrap_inner_root, 'etc/resolv.conf')
        filter_copy_resolv_conf(self._messenger, self._abs_resolv_conf, target)

    def _initialize_pacman_keyring(self, abs_pacstrap_inner_root):
        self._messenger.info('Initializing pacman keyring... (may take 2 to 7 minutes)')
        before = datetime.datetime.now()

        env = self._make_chroot_env()

        cmd = [
                COMMAND_UNSHARE,
                '--fork', '--pid',  # to auto-kill started gpg-agent
                COMMAND_CHROOT,
                abs_pacstrap_inner_root,
                'pacman-key',
                '--init',
                ]
        self._executor.check_call(cmd, env=env)

        cmd = [
                COMMAND_UNSHARE,
                '--fork', '--pid',  # to auto-kill started gpg-agent
                COMMAND_CHROOT,
                abs_pacstrap_inner_root,
                'pacman-key',
                '--populate', 'archlinux',
                ]
        self._executor.check_call(cmd, env=env)

        after = datetime.datetime.now()
        self._messenger.info('Took %d seconds.' % (after - before).total_seconds())

    def _run_pacstrap(self, abs_pacstrap_inner_root, rel_pacstrap_target_dir):
        self._messenger.info('Pacstrapping into "%s"...'
                % (os.path.join(abs_pacstrap_inner_root, rel_pacstrap_target_dir)))
        env = self._make_chroot_env()
        cmd = [
                COMMAND_CHROOT,
                abs_pacstrap_inner_root,
                'pacstrap',
                os.path.join('/', rel_pacstrap_target_dir),
                ]
        self._executor.check_call(cmd, env=env)

    def _mount_disk_chroot_mounts(self, abs_pacstrap_target_dir):
        self._executor.check_call([
                COMMAND_MOUNT,
                '-o', 'bind',
                self._abs_target_dir,
                abs_pacstrap_target_dir,
                ])

    def _mount_nondisk_chroot_mounts(self, abs_pacstrap_inner_root):
        self._messenger.info('Mounting non-disk file systems...')
        for source, options, target in _NON_DISK_MOUNT_TASKS:
            self._executor.check_call([
                    COMMAND_MOUNT,
                    source,
                    ] \
                    + options \
                    + [
                        os.path.join(abs_pacstrap_inner_root, target),
                    ])

    def _unmount_disk_chroot_mounts(self, abs_pacstrap_target_dir):
        try_unmounting(self._executor, abs_pacstrap_target_dir)

    def _unmount_nondisk_chroot_mounts(self, abs_pacstrap_inner_root):
        self._messenger.info('Unmounting non-disk file systems...')
        for source, options, target in reversed(_NON_DISK_MOUNT_TASKS):
            abs_path = os.path.join(abs_pacstrap_inner_root, target)
            try_unmounting(self._executor, abs_path)

    def run(self):
        self._ensure_directory_writable(self._abs_cache_dir, 0755)

        self._ensure_directory_writable(self._abs_target_dir, 0700)

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
            self._adjust_pacman_mirror_list(abs_pacstrap_inner_root)
            self._copy_etc_resolv_conf(abs_pacstrap_inner_root)


            rel_pacstrap_target_dir = os.path.join('mnt', 'arch_root', '')
            abs_pacstrap_target_dir = os.path.join(abs_pacstrap_inner_root, rel_pacstrap_target_dir)

            os.makedirs(abs_pacstrap_target_dir)

            self._mount_disk_chroot_mounts(abs_pacstrap_target_dir)
            try:
                self._mount_nondisk_chroot_mounts(abs_pacstrap_inner_root)
                try:
                    self._initialize_pacman_keyring(abs_pacstrap_inner_root)
                    self._run_pacstrap(abs_pacstrap_inner_root, rel_pacstrap_target_dir)
                finally:
                    self._unmount_nondisk_chroot_mounts(abs_pacstrap_inner_root)
            finally:
                self._unmount_disk_chroot_mounts(abs_pacstrap_target_dir)

        finally:
            self._messenger.info('Cleaning up "%s"...' % abs_temp_dir)
            shutil.rmtree(abs_temp_dir)

    @classmethod
    def add_arguments_to(clazz, distro):
        distro.add_argument('--image-date', type=date_argparse_type, metavar='YYYY-MM-DD',
                help='date to use boostrap image of (e.g. 2015-05-01, default: latest available)')
        distro.add_argument('--cache-dir', metavar='DIRECTORY', default='/var/cache/directory-bootstrap/',
                help='directory to use for downloads (default: %(default)s)')
        distro.add_argument('--mirror', dest='mirror_url', metavar='URL',
                default='http://mirror.rackspace.com/archlinux/$repo/os/$arch',
                help='pacman mirror to use (default: %(default)s)')

    @classmethod
    def create(clazz, messenger, executor, options):
        return clazz(
                messenger,
                executor,
                os.path.abspath(options.target_dir),
                os.path.abspath(options.cache_dir),
                options.architecture,
                options.image_date,
                options.mirror_url,
                os.path.abspath(options.resolv_conf),
                )
