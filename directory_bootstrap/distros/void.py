import errno
import os
import shutil
import tempfile
from tarfile import TarFile

from directory_bootstrap.distros.base import DirectoryBootstrapper
from directory_bootstrap.shared.commands import (
    COMMAND_CP,
    COMMAND_TAR,
    COMMAND_UNXZ,
    )


SUPPORTED_ARCHITECTURES = ('i686', 'x86_64')


class VoidBootstrapper(DirectoryBootstrapper):
    DISTRO_KEY = 'void'
    DISTRO_NAME_LONG = 'Void Linux'

    def __init__(self, messenger, executor, abs_target_dir, abs_cache_dir,
                architecture,
                abs_resolv_conf):
        super(VoidBootstrapper, self).__init__(
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
                COMMAND_CP,
                COMMAND_TAR,
                COMMAND_UNXZ,
                ]

    def _download_static_image(self):
        basename = 'xbps-static-latest.%s-musl.tar.xz' % self._architecture
        url = 'https://alpha.de.repo.voidlinux.org/static/%s' % basename
        abs_filename = os.path.join(self._abs_cache_dir, basename)
        self.download_url_to_file(url, abs_filename)
        return self.uncompress_xz_tarball(abs_filename)

    def _copy_keys_into_chroot(self, abs_temp_dir):
        rel_xbps_keys_path = 'var/db/xbps/keys'
        abs_target_xbps_keys_path = os.path.join(self._abs_target_dir, rel_xbps_keys_path)

        self._messenger.info('Copying xbps keys to "%s"...' % abs_target_xbps_keys_path)
        try:
            os.makedirs(abs_target_xbps_keys_path, 0o755)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        self._executor.check_call([
                COMMAND_CP,
                '-r',
                os.path.join(abs_temp_dir, rel_xbps_keys_path),
                os.path.dirname(abs_target_xbps_keys_path),
                ])

    def run(self):
        self.ensure_directories_writable()

        abs_temp_dir = os.path.abspath(tempfile.mkdtemp())
        try:
            abs_static_image_filename = self._download_static_image()
            with TarFile.open(abs_static_image_filename) as tf:
                tf.extractall(path=abs_temp_dir)

            self._copy_keys_into_chroot(abs_temp_dir)

            self._messenger.info('Installing into "%s"...' % self._abs_target_dir)
            xbps_install = os.path.join(abs_temp_dir, 'usr/bin/xbps-install.static')
            self._executor.check_call([
                    xbps_install,
                    '--rootdir', self._abs_target_dir,
                    '--repository=https://alpha.de.repo.voidlinux.org/current/musl',
                    '--sync', '--yes',
                    'base-system',
                    ], cwd=abs_temp_dir)
        finally:
            self._messenger.info('Cleaning up "%s"...' % abs_temp_dir)
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
