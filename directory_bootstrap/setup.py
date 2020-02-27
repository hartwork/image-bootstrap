#! /usr/bin/env python3
# Copyright (C) 2018 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from textwrap import dedent

from setuptools import setup


if __name__ == '__main__':
    setup(
            name='directory-bootstrap',
            description='Command line tool for creating chroots',
            long_description=open('setup-pypi-readme.rst', 'r').read(),
            license='AGPL v3 or later',
            version='1',
            author='Sebastian Pipping',
            author_email='sebastian@pipping.org',
            url='https://github.com/hartwork/image-bootstrap',
            install_requires=[
                'image-bootstrap',
            ],
            classifiers=[
                'Development Status :: 4 - Beta',
                'Environment :: Console',
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
