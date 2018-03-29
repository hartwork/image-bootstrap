import os
import re
import shutil
import tempfile
from tarfile import TarFile

from directory_bootstrap.distros.base import DirectoryBootstrapper


SUPPORTED_ARCHITECTURES = ('i686', 'x86_64')


class AlpineBootstrapper(DirectoryBootstrapper):
    DISTRO_KEY = 'alpine'
    DISTRO_NAME_LONG = 'Alpine Linux'

    __version_extractor = re.compile(
        'Current Alpine Version <strong>(?P<version>[0-9][^<]+)</strong>')

    class VersionException(Exception):
        pass

    def __init__(self, messenger, executor, abs_target_dir, abs_cache_dir,
                architecture,
                abs_resolv_conf):
        super(AlpineBootstrapper, self).__init__(
                messenger,
                executor,
                abs_target_dir,
                abs_cache_dir,
                )
        self._architecture = architecture
        self._abs_resolv_conf = abs_resolv_conf

    def wants_to_be_unshared(self):
        return True

    def _determine_latest_version(self):
        downloads_page_html = self.get_url_content('https://alpinelinux.org/downloads/')

        match = self.__version_extractor.search(downloads_page_html)
        if match is None:
            raise VersionException('Could not determine latest release version.')

        return match.group('version')

    @staticmethod
    def _parse_version(version_str):
        version_tuple = version_str.split('.')
        if len(version_tuple) < 3:
            raise VersionException('Version "{}" has unsupported format'.format(version_str))

        return version_tuple

    @staticmethod
    def _create_tarball_download_url(version_tuple, arch):
        return ('http://dl-cdn.alpinelinux.org/alpine/v{major}.{minor}/releases/{arch}/alpine-minirootfs-{major}.{minor}.{patch}-{arch}.tar.gz'
                .format(major=version_tuple[0],
                        minor=version_tuple[1],
                        patch=version_tuple[2], arch=arch))

    def _download_file(self, url):
        basename = url.split('/')[-1]
        abs_filename = os.path.join(self._abs_cache_dir, basename)
        self.download_url_to_file(url, abs_filename)
        return abs_filename

    def run(self):
        self.ensure_directories_writable()

        self._messenger.info('Searching for latest release...')
        version_str = self._determine_latest_version()
        version_tuple = self._parse_version(version_str)
        self._messenger.info('Found {} to be latest.'.format(version_str))

        tarball_download_url = self._create_tarball_download_url(
            version_tuple, self._architecture)

        abs_filename_tarball = self._download_file(tarball_download_url)

        self._messenger.info('Extracting to "{}"...'.format(self._abs_target_dir))
        with TarFile.open(abs_filename_tarball) as tf:
            tf.extractall(path=self._abs_target_dir)

    @classmethod
    def add_arguments_to(clazz, distro):
        distro.add_argument('--arch', dest='architecture', default='x86_64',
                choices=SUPPORTED_ARCHITECTURES,
                help='architecture (e.g. x86_64)')

    @classmethod
    def create(clazz, messenger, executor, options):
        return clazz(
                messenger,
                executor,
                os.path.abspath(options.target_dir),
                os.path.abspath(options.cache_dir),
                options.architecture,
                os.path.abspath(options.resolv_conf),
                )
