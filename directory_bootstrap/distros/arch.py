# -*- coding: UTF-8 -*-
# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import datetime
import os
import re
import shutil
import tempfile
from collections import namedtuple
from tarfile import TarFile

import directory_bootstrap.resources.arch as resources
from directory_bootstrap.distros.base import (
        DirectoryBootstrapper, date_argparse_type)
from directory_bootstrap.shared.commands import (
        COMMAND_CHROOT, COMMAND_GPG, COMMAND_MOUNT, COMMAND_TAR,
        COMMAND_UMOUNT, COMMAND_UNSHARE)
from directory_bootstrap.shared.loaders._pkg_resources import resource_filename
from directory_bootstrap.shared.mount import try_unmounting
from directory_bootstrap.shared.resolv_conf import filter_copy_resolv_conf

SUPPORTED_ARCHITECTURES = ('i686', 'x86_64')

_NON_DISK_MOUNT_TASKS = (
        ('/dev', ['-o', 'bind'], 'dev'),
        ('/dev/pts', ['-o', 'bind'], 'dev/pts'),  # for gpgme
        ('PROC', ['-t', 'proc'], 'proc'),  # for pacstrap mountpoint detection
        )


_year = '([2-9][0-9]{3})'
_month = '(0[1-9]|1[0-2])'
_day = '(0[1-9]|[12][0-9]|3[01])'

_keyring_package_date_matcher = re.compile('%s%s%s' % (_year, _month, _day))
_image_date_matcher = re.compile('%s\\.%s\\.%s' % (_year, _month, _day))


class ArchBootstrapper(DirectoryBootstrapper):
    DISTRO_KEY = 'arch'
    DISTRO_NAME_LONG = 'Arch Linux'

    def __init__(self, messenger, executor, abs_target_dir, abs_cache_dir,
                architecture, image_date_triple_or_none, mirror_url,
                abs_resolv_conf):
        super(ArchBootstrapper, self).__init__(
                messenger,
                executor,
                abs_target_dir,
                abs_cache_dir,
                )
        self._architecture = architecture
        self._image_date_triple_or_none = image_date_triple_or_none
        self._mirror_url = mirror_url
        self._abs_resolv_conf = abs_resolv_conf

    def wants_to_be_unshared(self):
        return True

    @staticmethod
    def get_commands_to_check_for():
        return DirectoryBootstrapper.get_commands_to_check_for() + [
                COMMAND_CHROOT,
                COMMAND_GPG,
                COMMAND_MOUNT,
                COMMAND_TAR,
                COMMAND_UMOUNT,
                ]

    def _get_keyring_listing(self):
        self._messenger.info('Downloading keyring listing...')
        return self.get_url_content('https://sources.archlinux.org/other/archlinux-keyring/')

    def _get_image_listing(self):
        self._messenger.info('Downloading image listing...')
        return self.get_url_content('https://mirrors.kernel.org/archlinux/iso/')

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

    def _import_gpg_keyring(self, abs_temp_dir, abs_gpg_home_dir, package_filename, package_yyyymmdd):
        rel_archlinux_gpg_path = 'archlinux-keyring-%s/archlinux.gpg' % package_yyyymmdd
        with TarFile.open(package_filename) as tf:
            tf.extract(rel_archlinux_gpg_path, path=abs_temp_dir)
        abs_archlinux_gpg_path = os.path.join(abs_temp_dir, rel_archlinux_gpg_path)

        self._import_gpg_key_file(abs_gpg_home_dir, abs_archlinux_gpg_path)

    def _import_gpg_keys(self, abs_gpg_home_dir, key_ids):
        for key_id in key_ids:
            cmd = self._get_gpg_argv_start(abs_gpg_home_dir) + [
                    '--receive-keys', key_id,
                ]
            self._executor.check_call(cmd)

    def _extract_image(self, image_filename, abs_temp_dir):
        abs_pacstrap_outer_root = os.path.join(abs_temp_dir, 'pacstrap_root', '')

        self._messenger.info('Extracting bootstrap image to "%s"...' % abs_pacstrap_outer_root)
        abs_pacstrap_inner_root = os.path.join(abs_pacstrap_outer_root, 'root.%s' % self._architecture)

        os.makedirs(abs_pacstrap_outer_root)
        self._executor.check_call([COMMAND_TAR,
                                   'xf', image_filename,
                                   '-C', abs_pacstrap_outer_root,
                                   ])

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

    def _obtain_keys_allowed_to_sign_archlinux_keyring_tarball(self):
        pkgbuild_content = self.get_url_content('https://git.archlinux.org/svntogit/packages.git/plain/trunk/PKGBUILD?h=packages/archlinux-keyring')
        long_key_id_matcher = re.compile('\\b(?P<long_key_id>[0-9a-fA-F]{40})\\b.*# (?P<comment>.+)')

        KeyInfo = namedtuple('KeyInfo', ['long_key_id', 'comment'])

        inside = False
        key_infos = []
        for line in pkgbuild_content.split('\n'):
            if not inside:
                if line.startswith('validpgpkeys='):
                    inside = True

            if inside:
                m = long_key_id_matcher.search(line)
                if m:
                    key_infos.append(KeyInfo(**m.groupdict()))
                if ')' in line:
                    break
        return key_infos

    def run(self):
        self.ensure_directories_writable()

        abs_temp_dir = os.path.abspath(tempfile.mkdtemp())
        try:
            if self._image_date_triple_or_none is None:
                image_listing_html = self._get_image_listing()
                image_yyyy_mm_dd = self.extract_latest_date(image_listing_html, _image_date_matcher)
            else:
                image_yyyy_mm_dd = '%04s.%02d.%02d' % self._image_date_triple_or_none

            keyring_listing_html = self._get_keyring_listing()
            package_yyyymmdd = self.extract_latest_date(keyring_listing_html, _keyring_package_date_matcher)

            package_sig_filename = self._download_keyring_package(package_yyyymmdd, '.sig')
            package_filename = self._download_keyring_package(package_yyyymmdd)

            abs_gpg_home_dir = self._initialize_gpg_home(abs_temp_dir)

            self._messenger.info('Importing GPG keys whitelisted to sign archlinux-keyring...')

            key_infos = self._obtain_keys_allowed_to_sign_archlinux_keyring_tarball()
            self._messenger.info('Keys found allowed to sign archlinux-keyring tarball:')
            for key in sorted(key_infos, key=lambda x: (x.comment, x.long_key_id)):
                self._messenger.info('  - %s (%s)' % (key.comment, key.long_key_id))
            remote_key_ids = {k.long_key_id for k in key_infos}
            on_disk_key_ids = {
                # https://git.archlinux.org/svntogit/packages.git/tree/trunk/PKGBUILD?h=packages/archlinux-keyring
                '4AA4767BBC9C4B1D18AE28B77F2D434B9741E8AC',  # Pierre Schmitz <pierre@archlinux.de>
                'A314827C4E4250A204CE6E13284FC34C8E4B1A25',  # Thomas Bächler <thomas@bchlr.de>
                '86CFFCA918CF3AF47147588051E8B148A9999C34',  # Evangelos Foutras <evangelos@foutrelis.com>
                'F3691687D867B81B51CE07D9BBE43771487328A9',  # Bartlomiej Piotrowski <b@bpiotrowski.pl>
                'BD84DE71F493DF6814B0167254EDC91609BC9183',  # Christian Hesse <Christi@n-Hes.se>
                'CFA6AF15E5C74149FC1D8C086D1655C14CE1C13E',  # Florian Pritz <bluewind@xinu.at>
                'E499C79F53C96A54E572FEE1C06086337C50773E',  # Jelle van der Waa <jelle@archlinux.org>
            }

            load_from_web_key_ids = remote_key_ids - on_disk_key_ids
            load_from_disk_key_ids = remote_key_ids - load_from_web_key_ids

            self._messenger.info('Importing GPG keys from the internet...')
            self._import_gpg_keys(abs_gpg_home_dir, load_from_web_key_ids)

            self._messenger.info('Importing GPG keys from disk...')
            for key_id in load_from_disk_key_ids:
                abs_key_path = resource_filename(resources.__name__, '%s.asc' % key_id)
                self._import_gpg_key_file(abs_gpg_home_dir, abs_key_path)

            self._verify_file_gpg(package_filename, package_sig_filename, abs_gpg_home_dir)

            self._import_gpg_keyring(abs_temp_dir, abs_gpg_home_dir, package_filename, package_yyyymmdd)

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
        distro.add_argument('--arch', dest='architecture', default='x86_64',
                choices=SUPPORTED_ARCHITECTURES,
                help='architecture (e.g. x86_64)')
        distro.add_argument('--image-date', type=date_argparse_type, metavar='YYYY-MM-DD',
                help='date to use boostrap image of (e.g. 2015-05-01, default: latest available)')
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
