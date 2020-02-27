# Copyright (C) 2016 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later



import os
import re
import urllib.request, urllib.parse, urllib.error

from textwrap import dedent

from directory_bootstrap.distros.yum_based import YumBasedDirectoryBootstrapper
from directory_bootstrap.shared.loaders._bs4 import BeautifulSoup


def _abs_filename_to_url(abs_filename):
    return 'file://%s' % urllib.request.pathname2url(abs_filename)


class CentOsBootstrapper(YumBasedDirectoryBootstrapper):
    DISTRO_KEY = 'centos'
    DISTRO_NAME_LONG = 'CentOS'

    EXAMPLE_RELEASE = '7.4.1708'  # 2017-12-29

    def _write_yum_conf(self, abs_yum_conf_path, abs_gpg_public_key_filename):
        self._messenger.info('Writing file "%s"...' % abs_yum_conf_path)
        gpg_public_key_file_url = _abs_filename_to_url(abs_gpg_public_key_filename)
        with open(abs_yum_conf_path, 'w') as f:
            print(dedent("""\
                    [base]
                    name=CentOS-$releasever - Base
                    baseurl=http://mirror.centos.org/centos/$releasever/os/$basearch/
                    gpgcheck=1
                    gpgkey=%(gpgkey)s

                    #released updates
                    [updates]
                    name=CentOS-$releasever - Updates
                    baseurl=http://mirror.centos.org/centos/$releasever/updates/$basearch/
                    gpgcheck=1
                    gpgkey=%(gpgkey)s

                    #additional packages that may be useful
                    [extras]
                    name=CentOS-$releasever - Extras
                    baseurl=http://mirror.centos.org/centos/$releasever/extras/$basearch/
                    gpgcheck=1
                    gpgkey=%(gpgkey)s
                    """ % {
                        'gpgkey': gpg_public_key_file_url,
                    }), file=f)

    def _find_latest_release(self):
        html = self.get_url_content('https://wiki.centos.org/Download')
        soup = BeautifulSoup(html, 'lxml')

        minor_version_matcher = re.compile('^ ?([0-9]+) \(([0-9]+)\) ?$')

        candidates = []
        prev = None
        for paragraph in soup.find_all('p'):
            m = minor_version_matcher.match(paragraph.text)
            if not m:
                prev = paragraph
                continue

            try:
                mayor_version = int(prev.text.strip())
            except ValueError:
                prev = paragraph
                continue

            if mayor_version > 7:
                # CentOS >=8 needs DNF and we only support YUM right now
                continue

            version = '%s.%s.%s' % (mayor_version, m.group(1), m.group(2))
            candidates.append(version)

        return sorted(candidates)[-1]

    def _download_release_public_key(self):
        self._messenger.info('Downloading related GnuPG public key...')
        release_major = self._releasever.split('.')[0]
        if int(release_major) > 7:
            rel_gpg_public_key_filename = 'RPM-GPG-KEY-CentOS-Official'
        else:
            rel_gpg_public_key_filename = 'RPM-GPG-KEY-CentOS-%s' % release_major
        abs_gpg_public_key_filename = os.path.join(self._abs_cache_dir, rel_gpg_public_key_filename)
        self.download_url_to_file(
                'https://www.centos.org/keys/%s' % rel_gpg_public_key_filename,
                abs_gpg_public_key_filename)
        return abs_gpg_public_key_filename
