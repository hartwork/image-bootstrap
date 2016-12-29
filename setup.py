#! /usr/bin/env python2
# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from setuptools import find_packages, setup

from directory_bootstrap.shared.metadata import (
        GITHUB_HOME_URL, PACKAGE_NAME, VERSION_STR)


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
            install_requires=[
                'beautifulsoup4',
                'colorama',
                'lxml',
                'requests',
                'setuptools',
                'PyYAML',
            ],
            packages=[
                p for p in find_packages() if not p.endswith('.test')
            ],
            entry_points={
                'console_scripts': [
                    'directory-bootstrap = directory_bootstrap.cli:main',
                    'image-bootstrap = image_bootstrap.cli:main'
                ],
            },
            classifiers=[
                'Development Status :: 4 - Beta',
                'Environment :: Console',
                'Environment :: OpenStack',
                'Intended Audience :: Developers',
                'Intended Audience :: End Users/Desktop',
                'Intended Audience :: System Administrators',
                'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
                'Natural Language :: English',
                'Operating System :: POSIX :: Linux',
                'Programming Language :: Python :: 2.7',
                'Topic :: System :: Installation/Setup',
                'Topic :: Utilities',
            ],
    )
