#! /usr/bin/env python2
# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from distutils.core import setup

from directory_bootstrap.shared.metadata import GITHUB_HOME_URL, PACKAGE_NAME, VERSION_STR


_PYTHON_PACKAGE_NAME = PACKAGE_NAME.replace('-','_')


if __name__ == '__main__':
    setup(
            name=PACKAGE_NAME,
            description='Command line tool for creating bootable virtual machine images',
            license='AGPL v3 or later',
            version=VERSION_STR,
            author='Sebastian Pipping',
            author_email='sebastian@pipping.org',
            url=GITHUB_HOME_URL,
            download_url='%s/archive/%s.tar.gz' % (GITHUB_HOME_URL, VERSION_STR),
            packages=[
                _PYTHON_PACKAGE_NAME,
                '%s.distros' % _PYTHON_PACKAGE_NAME,
                '%s.types' % _PYTHON_PACKAGE_NAME,
                'directory_bootstrap',
                'directory_bootstrap.distros',
                'directory_bootstrap.shared',
                'directory_bootstrap.shared.loaders',
            ],
            data_files=[
                ('sbin/', [PACKAGE_NAME, 'directory-bootstrap']),
            ],
            classifiers=[
                'Development Status :: 4 - Beta',
                'Environment :: Console',
                'Intended Audience :: Developers',
                'Intended Audience :: End Users/Desktop',
                'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
                'Natural Language :: English',
                'Operating System :: POSIX :: Linux',
                'Programming Language :: Python',
                'Topic :: System :: Installation/Setup',
                'Topic :: Utilities',
            ],
            )
