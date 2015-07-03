# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import os

from directory_bootstrap.distros.base import DirectoryBootstrapper


_DEFAULT_MIRROR = 'http://distfiles.gentoo.org/'


class GentooBootstrapper(DirectoryBootstrapper):
    DISTRO_KEY = 'gentoo'

    def __init__(self, messenger, executor, abs_target_dir, abs_cache_dir,
                architecture, mirror_url,
                abs_resolv_conf):
        self._messenger = messenger
        self._executor = executor
        self._abs_target_dir = abs_target_dir
        self._abs_cache_dir = abs_cache_dir
        self._architecture = architecture
        self._mirror_base_url = mirror_url.rstrip('/')
        self._abs_resolv_conf = abs_resolv_conf

    @staticmethod
    def get_commands_to_check_for():
        return DirectoryBootstrapper.get_commands_to_check_for()

    def _get_stage3_listing_url(self):
        return '%s/releases/%s/autobuilds/' % (self._mirror_base_url, self._architecture)

    def _get_portage_snapshot_listing_url(self):
        return '%s/releases/snapshots/current/' % self._mirror_base_url

    def _find_latest_stage3_date(self, stage3_listing):
        raise NotImplementedError()

    def _find_latest_snapshot_date(self, snapshot_listing):
        raise NotImplementedError()

    def _download_stage3(self, stage3_date_str):
        res = [None, None, None]
        for target_index, basename in (
                (2, 'stage3-amd64-%s.tar.bz2.DIGESTS.asc' % stage3_date_str),
                (1, 'stage3-amd64-%s.tar.bz2.DIGESTS' % stage3_date_str),
                (0, 'stage3-amd64-%s.tar.bz2' % stage3_date_str),
                ):
            filename = os.path.join(self._abs_cache_dir, basename)
            url = '%s/releases/%s/autobuilds/%s/%s' \
                    % (self._mirror_base_url, self._architecture, stage3_date_str, basename)
            self.download_url_to_file(url, filename)

            assert res[target_index] is None
            res[target_index] = filename

        return res

    def _download_snapshot(self, snapshot_date_str):
        res = [None, None, None, None]
        for target_index, basename in (
                (1, 'portage-%s.tar.xz.gpgsig' % snapshot_date_str),
                (2, 'portage-%s.tar.xz.md5sum' % snapshot_date_str),
                (3, 'portage-%s.tar.xz.umd5sum' % snapshot_date_str),
                (0, 'portage-%s.tar.xz' % snapshot_date_str),
                ):
            filename = os.path.join(self._abs_cache_dir, basename)
            url = '%s/releases/snapshots/current/%s' \
                    % (self._mirror_base_url, basename)
            self.download_url_to_file(url, filename)

            assert res[target_index] is None
            res[target_index] = filename

        return res

    def _verify_gpg_signature(self, testee_file, signature_file):
        raise NotImplementedError()

    def _verify_sha512_sum(self, stage3_tarball, stage3_digests):
        raise NotImplementedError()

    def _verify_md5_sum(self, snapshot_tarball, snapshot_md5sum):
        raise NotImplementedError()

    def _uncompress_tarball(self, tarball_filename):
        raise NotImplementedError()

    def _extract_tarball(self, tarball_filename, abs_target_root):
        raise NotImplementedError()

    def run(self):
        stage3_listing = self.get_url_content(self._get_stage3_listing_url())
        snapshot_listing = self.get_url_content(self._get_portage_snapshot_listing_url())

        latest_stage3_date_str = self._find_latest_stage3_date(stage3_listing)
        latest_snapshot_date_str = self._find_latest_snapshot_date(snapshot_listing)

        stage3_tarball, stage3_digests, stage3_digests_asc \
                = self._download_stage3(latest_stage3_date_str)

        snapshot_tarball, snapshot_gpgsig, snapshot_md5sum, snapshot_uncompressed_md5sum \
                = self._download_snapshot(latest_snapshot_date_str)

        snapshot_tarball_uncompressed = self._uncompress_tarball(snapshot_tarball)

        self._verify_gpg_signature(stage3_digests, stage3_digests_asc)
        self._verify_gpg_signature(stage3_md5sum, stage3_gpgsig)
        self._verify_gpg_signature(stage3_unpacked_md5sum, stage3_gpgsig)

        self._verify_sha512_sum(stage3_tarball, stage3_digests)
        self._verify_md5_sum(snapshot_tarball, snapshot_md5sum)
        self._verify_md5_sum(snapshot_tarball_uncompressed, snapshot_uncompressed_md5sum)

        self._extract_tarball(stage3_tarball, self._abs_target_dir)
        self._extract_tarball(snapshot_tarball_uncompressed, os.path.join(self._abs_target_dir, 'usr/portage'))

    @classmethod
    def add_arguments_to(clazz, distro):
        distro.add_argument('--arch', dest='architecture', default='amd64',
                help='architecture (e.g. amd64)')
        distro.add_argument('--mirror', dest='mirror_url', metavar='URL',
                default=_DEFAULT_MIRROR,
                help='mirror to use (default: %(default)s)')

    @classmethod
    def create(clazz, messenger, executor, options):
        return clazz(
                messenger,
                executor,
                os.path.abspath(options.target_dir),
                os.path.abspath(options.cache_dir),
                options.architecture,
                options.mirror_url,
                os.path.abspath(options.resolv_conf),
                )
