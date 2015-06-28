#! /bin/bash
# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

on_exit() {
	echo FAILED 1>&2
}
trap on_exit exit


FAIL_USAGE() {
	echo "USAGE: $(basename "$0") BLOCK_DEV ROOT_PASSWORD" 1>&2
	exit 1
}


DEBIAN_MIRROR_URL=http://ftp.de.debian.org/debian/
HTTP_PROXY_URL=http://127.0.0.1:8123/  # polipo


if [[ ! -b "$1" ]]; then
	FAIL_USAGE
fi
target_device="$1"; shift

if [[ -z "$1" ]]; then
	FAIL_USAGE
fi
root_password="$1"; shift


if [[ "$(id -u)" -ne 0 ]]; then
	echo "ERROR: Yo do not seem to be root (user ID 0)." 1>&2
	exit 1
fi


ECHO_RUN() {
	echo '#' "$@"
	"$@"
}

BUILD() {
	name="$1"; shift
	ECHO_RUN env http_proxy="${HTTP_PROXY_URL}" ./image-bootstrap --verbose --password "${root_password}" "$@" "${target_device}"
}


set -e


BUILD arch-openstack \
	--openstack arch
BUILD debian-wheezy \
	--bootloader host-grub2-drive debian --release wheezy --mirror "${DEBIAN_MIRROR_URL}"
BUILD debian-jessie-openstack \
	--openstack debian --release jessie --mirror "${DEBIAN_MIRROR_URL}"
BUILD ubuntu-vivid \
	ubuntu --release vivid


trap - exit
echo PASSED
