import os
import re
import shutil
import tempfile
from tarfile import TarFile

import directory_bootstrap.resources.alpine as resources
from directory_bootstrap.distros.base import DirectoryBootstrapper
from directory_bootstrap.shared.commands import COMMAND_GPG, COMMAND_UNSHARE
from directory_bootstrap.shared.loaders._pkg_resources import resource_filename


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

    @staticmethod
    def get_commands_to_check_for():
        return DirectoryBootstrapper.get_commands_to_check_for() + [
                COMMAND_GPG,
                COMMAND_UNSHARE,
                ]

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
        signatur_download_url = '{}.asc'.format(tarball_download_url)

        # Signature first, so we fail earlier if we do
        abs_filename_signature = self._download_file(signatur_download_url)
        abs_filename_tarball = self._download_file(tarball_download_url)

        abs_temp_dir = os.path.abspath(tempfile.mkdtemp())
        try:
            abs_gpg_home_dir = self._initialize_gpg_home(abs_temp_dir)
            release_pubring_gpg = resource_filename(resources.__name__,
                                                    'ncopa.asc')
            self._import_gpg_key_file(abs_gpg_home_dir, release_pubring_gpg)
            self._verify_file_gpg(abs_filename_tarball,
                                  abs_filename_signature, abs_gpg_home_dir)

            self._messenger.info('Extracting to "{}"...'.format(self._abs_target_dir))
            with TarFile.open(abs_filename_tarball) as tf:
                tf.extractall(path=self._abs_target_dir)
        finally:
            self._messenger.info('Cleaning up "{}"...'.format(abs_temp_dir))
            shutil.rmtree(abs_temp_dir)

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
