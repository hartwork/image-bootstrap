# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import os
from argparse import ArgumentParser

from image_bootstrap.distros.debian import BootstrapDebian, DISTRO_KEY
from image_bootstrap.messenger import Messenger
from image_bootstrap.executor import Executor


def main():
    parser = ArgumentParser()
    parser.add_argument('--hostname', required=True)
    parser.add_argument('--arch', dest='architecture', default='amd64')
    parser.add_argument('--password', dest='root_password')  # TODO
    parser.add_argument('--verbose', action='store_true')

    distros = parser.add_argument_group('Choice of distribution')
    distros.add_argument('--debian', dest='distribution', action='store_const', const=DISTRO_KEY, required=True)

    debian = parser.add_argument_group('Debian')
    debian.add_argument('--release', dest='debian_release', default='wheezy', choices=['wheezy', 'jessie', 'sid'])
    debian.add_argument('--mirror', dest='debian_mirror_url', default='http://http.debian.net/debian')

    parser.add_argument('--scripts-pre', dest='scripts_dir_pre')
    parser.add_argument('--scripts-chroot', dest='scripts_dir_chroot')
    parser.add_argument('--scripts-post', dest='scripts_dir_post')

    parser.add_argument('target_path', metavar='DEVICE')

    options = parser.parse_args()

    messenger = Messenger(bool(options.verbose))
    executor = Executor(messenger)

    bootstrap = BootstrapDebian(
            messenger,
            executor,
            options.hostname,
            options.architecture,
            options.root_password,
            options.debian_release,
            options.debian_mirror_url,
            os.path.abspath(options.scripts_dir_pre),
            os.path.abspath(options.scripts_dir_chroot),
            os.path.abspath(options.scripts_dir_post),
            os.path.abspath(options.target_path),
            )
    bootstrap.run()


if __name__ == '__main__':
    main()
