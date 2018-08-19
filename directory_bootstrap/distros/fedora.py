# Copyright (C) 2016 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import json
import os
import urllib

from textwrap import dedent

from directory_bootstrap.distros.yum_based import YumBasedDirectoryBootstrapper


_COLLECTIONS_URL = 'https://admin.fedoraproject.org/pkgdb/api/collections/'


def _abs_filename_to_url(abs_filename):
    return 'file://%s' % urllib.pathname2url(abs_filename)


class FedoraBootstrapper(YumBasedDirectoryBootstrapper):
    DISTRO_KEY = 'fedora'
    DISTRO_NAME_LONG = 'Fedora'

    EXAMPLE_RELEASE = 24

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

    def _download_release_public_key(self):
        self._messenger.info('Downloading related GnuPG public key...')
        rel_gpg_public_key_filename = 'RPM-GPG-KEY-fedora-%s-primary' \
                % self._releasever
        abs_gpg_public_key_filename = os.path.join(self._abs_cache_dir, rel_gpg_public_key_filename)
        self.download_url_to_file(
                'https://src.fedoraproject.org/rpms/fedora-repos/raw/master/f/%s' % rel_gpg_public_key_filename,
                abs_gpg_public_key_filename)
        return abs_gpg_public_key_filename
