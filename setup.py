#! /usr/bin/env python2
# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from distutils.core import setup

from image_bootstrap.metadata import GITHUB_HOME_URL, PACKAGE_NAME, VERSION_STR


if __name__ == '__main__':
    setup(
            name=PACKAGE_NAME,
            license='AGPL v3 or later',
            version=VERSION_STR,
            author='Sebastian Pipping',
            author_email='sebastian@pipping.org',
            url=GITHUB_HOME_URL,
            packages=[PACKAGE_NAME.replace('-','_')],
            data_files=[('sbin/', [PACKAGE_NAME])],
            )
