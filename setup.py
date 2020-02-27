#! /usr/bin/env python3
# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import glob
import os

from setuptools import find_packages, setup

from directory_bootstrap.shared.metadata import (
        GITHUB_HOME_URL, PACKAGE_NAME, VERSION_STR)


if __name__ == '__main__':
    setup(
            name=PACKAGE_NAME,
            description='Command line tool for creating bootable virtual machine images',
            long_description=open('README.md').read(),
            long_description_content_type='text/markdown',
            license='AGPL v3 or later',
            version=VERSION_STR,
            author='Sebastian Pipping',
            author_email='sebastian@pipping.org',
            url=GITHUB_HOME_URL,
            python_requires='>=3',
            setup_requires=[
                'setuptools>=38.6.0',  # for long_description_content_type
            ],
            install_requires=[
                'beautifulsoup4',
                'colorama',
                'lxml',
                'requests',
                'setuptools',
                'PyYAML',
            ],
            tests_require=[
                'pytest',
            ],
            packages=[
                p for p in find_packages() if not p.endswith('.test')
            ],
            package_data={
                'directory_bootstrap': [
                    'resources/alpine/ncopa.asc',
                ] + [
                    os.path.relpath(p, 'directory_bootstrap')
                    for p
                    in glob.glob('directory_bootstrap/resources/*/*.asc')
                ],
            },
            entry_points={
                'console_scripts': [
                    'directory-bootstrap = directory_bootstrap.__main__:main',
                    'image-bootstrap = image_bootstrap.__main__:main',
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
                'Programming Language :: Python',
                'Programming Language :: Python :: 3',
                'Programming Language :: Python :: 3.6',
                'Programming Language :: Python :: 3.7',
                'Programming Language :: Python :: 3.8',
                'Programming Language :: Python :: 3 :: Only',
                'Topic :: System :: Installation/Setup',
                'Topic :: Utilities',
            ],
            )
