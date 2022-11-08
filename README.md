[![Build Status](https://travis-ci.org/hartwork/image-bootstrap.svg?branch=master)](https://travis-ci.org/hartwork/image-bootstrap)

**Table of Contents**

* [About](#About)
* [History](#History)
* [Example run](#ExampleRun)
* [Speeding things up](#SpeedingThingsUp)
    * [Using RAM instead of HDD/SSD](#UsingRamInsteadOfDisk)
    * [Apt-Cacher NG -- a cache specific to Debian/Ubuntu](#AptCacherNG)
    * [Polipo -- a generic HTTP cache](#Polipo)
    * [haveged -- an entropy generator](#haveged)
* [Debian package](#DebianPackage)
* [Usage (`--help` output)](#HelpOutput)
* [Hints on using image-bootstrap within a pipe](#Piping)
* [Known limitations](#KnownLimitations)
    * [Installing to partition block devices](#PartitionBlockTarget)


<a name="About"></a>
# About

Welcome to the home of **image-bootstrap** (and its little brother **directory-bootstrap**).

**image-bootstrap** is a command line tool to generate bootable virtual machine images
and write them to a given _block device_.<br>
Linux distributions supported by **image-bootstrap** currently include:
Arch, Debian, Gentoo, Ubuntu.<br>
When passing the `--openstack` parameter, images are
[prepared for use with OpenStack](http://docs.openstack.org/image-guide/content/ch_openstack_images.html).

**directory-bootstrap** is a command line tool to install non-Debian Linux distributions
into a given _directory_ (similar to [debootstrap](https://wiki.debian.org/Debootstrap)
for Debian/Ubuntu).<br>
Distributions supported by **directory-bootstrap** currently include:
Alpine Linux, Arch Linux, Gentoo, and Void Linux.


<a name="History"></a>
# History

**image-bootstrap** started out as a re-write of
[grml-debootstrap](https://github.com/grml/grml-debootstrap).
Primarily, it can be used to create Debian/Ubuntu or Arch images ready to be launched as a virtual machine.

In comparision to grml-debootstrap, by now **image-bootstrap**

 * installs to block devices only,

 * supports several approaches to installing GRUB 2.x, or extlinux, or no bootloader at all,

 * does not leak the host's hostname into the resulting image,

 * supports passing the root password off the command-line
   (and the eyes of other users and shell history),

 * supports using a custom `/etc/resolv.conf` file
   (e.g. to not leak your home router model name from `/etc/resolv.conf` into the image),

 * has support for installing Arch Linux, Gentoo and Ubuntu (besides Debian),

 * is able to create
   [OpenStack images](http://docs.openstack.org/image-guide/content/ch_openstack_images.html),

 * is written in Python rather than Bash/mksh, and

 * has more friendly terminal output.

**directory-bootstrap** came into life with the arrival of support for Arch Linux.
Support for Gentoo followed, after.
Support for Void Linux ~and CentOS~ chroots came into live during 34c3, December 2017.
Support for Alpine Linux chroots came into in March 2018.


<a name="ExampleRun"></a>
# Example run

The following is a complete demo of installing Debian stretch to LVM volume `/dev/vg/lv`
and launching the resulting image using KVM.

```console
# ${EDITOR} root_password.txt

# sudo image-bootstrap --hostname stretch debian \
                                  --password-file root_password.txt /dev/vg/lv
     _                          __             __      __
    (_)_ _  ___ ____ ____  ___ / /  ___  ___  / /____ / /________ ____
   / /  ' \/ _ `/ _ `/ -_)/__// _ \/ _ \/ _ \/ __(_-</ __/ __/ _ `/ _ \
  /_/_/_/_/\_,_/\_, /\__/    /_.__/\___/\___/\__/___/\__/_/  \_,_/ .__/
               /___/                      v0.9.1 :: 2015-07-11  /_/

Software libre licensed under AGPL v3 or later.
Brought to you by Sebastian Pipping <sebastian@pipping.org>.
Please report bugs at https://github.com/hartwork/image-bootstrap.  Thank you!

Selected approach "chroot-grub2-drive" for bootloader installation.
Checking for blkid... /sbin/blkid
Checking for chmod... /bin/chmod
Checking for chroot... /usr/sbin/chroot
Checking for cp... /bin/cp
Checking for debootstrap... /usr/sbin/debootstrap
Checking for find... /usr/bin/find
Checking for kpartx... /sbin/kpartx
Checking for mkdir... /bin/mkdir
Checking for mkfs.ext4... /sbin/mkfs.ext4
Checking for mount... /bin/mount
Checking for parted... /sbin/parted
Checking for partprobe... /sbin/partprobe
Checking for rm... /bin/rm
Checking for rmdir... /bin/rmdir
Checking for sed... /bin/sed
Checking for tune2fs... /sbin/tune2fs
Checking for umount... /bin/umount
Checking for uname... /bin/uname
Checking for unshare... /usr/bin/unshare

Checking for known unsupported architecture/machine combination...
Checking if "/dev/vg/lv" is a block device...
Reading root password from file "/home/user1/root_password.txt"...
Unsharing Linux namespaces (mount, UTS/hostname)...
Partitioning "/dev/vg/lv"...
Activating partition devices...
Creating file system on "/dev/mapper/vg-lvp1"...
Creating directory "/mnt/tmpFczeFl"...
Mounting partitions...
Creating directory "/mnt/tmpFczeFl/etc"...
Writing file "/mnt/tmpFczeFl/etc/hostname"...
Writing file "/mnt/tmpFczeFl/etc/resolv.conf" (based on file "/etc/resolv.conf")...
Bootstrapping Debian "stretch" into "/mnt/tmpFczeFl"...
Writing file "/mnt/tmpFczeFl/etc/hostname"...
Writing file "/mnt/tmpFczeFl/etc/resolv.conf" (based on file "/etc/resolv.conf")...
Writing file "/mnt/tmpFczeFl/etc/fstab"...
Writing file "/mnt/tmpFczeFl/etc/network/interfaces"...
Running pre-chroot scripts...
Mounting non-disk file systems...
Setting root password...
Writing device map to "/mnt/tmpFczeFl/boot/grub/device.map" (mapping "(hd9999)" to "/dev/dm-8")...
Installing bootloader to device "/dev/vg/lv" (actually "/dev/dm-8", approach "chroot-grub2-drive")...
Generating GRUB configuration...
Post-processing GRUB config...
Generating initramfs...
Unmounting non-disk file systems...
Cleaning chroot apt cache...
Running post-chroot scripts...
Unmounting partitions...
Removing directory "/mnt/tmpFczeFl"...
Deactivating partition devices...
Done.

# sudo kvm -hda /dev/vg/lv
```

Without `--color never`, the output above is actually in color.


<a name="SpeedingThingsUp"></a>
# Speeding things up


<a name="UsingRamInsteadOfDisk"></a>
## Using RAM instead of HDD/SSD

If you run **image-bootstrap** repeatedly and have enough RAM, you may want to
create images on RAM storage rather than on disk.  I use a setup with

 * a loop device (to have a block device)

 * over a sparse file (to save space)

 * in a tmpfs mount (to use RAM).

For example (assuming you have /tmp in RAM already):

```console
# sudo mount -o remount,size=6g /tmp
# truncate --size 3g /tmp/disk3g
# LOOP_DEVICE="$(losetup --show -f /tmp/disk3g)"

# image-bootstrap .... arch ... "${LOOP_DEVICE}"
# qemu-img convert -p -f raw -O qcow2 "${LOOP_DEVICE}" /var/lib/arch-$(date -I).qcow2

# losetup -d "${LOOP_DEVICE}"
# rm /tmp/disk3g
```


<a name="AptCacherNG"></a>
## Apt-Cacher NG -- a cache specific to Debian/Ubuntu

When creating multiple images,
a local instance of [Apt-Cacher NG](https://www.unix-ag.uni-kl.de/~bloch/acng/) and
passing `--mirror http://localhost:3142/debian` to **image-bootstrap** may come in handy.

<a name="Polipo"></a>
## Polipo -- a generic HTTP cache

For a distribution-agnostic cache, using
[Polipo](https://github.com/jech/polipo) can greatly speed up consecutive runs.
Invoke **image-bootstrap** with

```console
# http_proxy=http://127.0.0.1:8123/ image-bootstrap ...
```

when using Polipo with default port configuration.

<a name="haveged"></a>
## haveged -- an entropy generator

During image creation, cryptographic keys may need to be generated, e.g.
for the OpenSSH server, at least temporarily.  As key generation relies
on availability of entropy, image creation may take longer in environments that
are slow at adding to the entropy pool.
To speed things up, running [haveged](http://www.issihosts.com/haveged/)
at the host system _could_ be an option, especially since all keys should be deleted
from images, eventually. Otherwise, there is a risk of ending up with multiple
systems having the same key allowing for attacks.
I am unsure of the quality of entropy that haveged produces.  Use is at your own risk.


<a name="DebianPackage"></a>
# Debian package

As long as **image-bootstrap** as not available _in_ Debian, you can
make an **image-bootstrap** Debian package yourself easily from Git as follows:

```console
# git clone https://github.com/hartwork/image-bootstrap.git
Cloning into 'image-bootstrap'...
[..]

# make -C image-bootstrap/ deb
[..]

# ls *.deb
image-bootstrap_0.9.1_all.deb

# sudo dpkg -i image-bootstrap_0.9.1_all.deb
[..]
```


<a name="HelpOutput"></a>
# Usage (`--help` output)

In general, the usage is:

```console
image-bootstrap [..] DISTRIBUTION [..] DEVICE
```

or

```console
image-bootstrap --hostname NAME [DISTRO_AGNOSTIC] DISTRIBUTION [DISTRO_SPECIFIC] DEVICE
```

in a bit more detail.


A dump of the current `--help` output would be:
```console
# image-bootstrap --help
usage: image-bootstrap [-h] [--version] [--color {never,always,auto}]
                       [--debug] [--quiet] [--verbose] [--arch ARCHITECTURE]
                       [--bootloader {auto,chroot-grub2-device,chroot-grub2-drive,host-extlinux,host-grub2-device,host-grub2-drive,none}]
                       [--bootloader-force] [--hostname NAME] [--openstack]
                       [--password PASSWORD | --password-file FILE]
                       [--resolv-conf FILE] [--disk-id ID]
                       [--first-partition-uuid UUID] [--machine-id ID]
                       [--scripts-pre DIRECTORY] [--scripts-chroot DIRECTORY]
                       [--scripts-post DIRECTORY] [--grub2-install COMMAND]
                       [--cache-dir DIRECTORY]
                       DISTRIBUTION ... DEVICE

Command line tool for creating bootable virtual machine images

positional arguments:
  DEVICE                block device to install to

optional arguments:
  -h, --help            show this help message and exit
  --version             show program's version number and exit

text output configuration:
  --color {never,always,auto}
                        toggle output color (default: auto)
  --debug               enable debugging
  --quiet               limit output to error messages
  --verbose             increase verbosity

machine configuration:
  --arch ARCHITECTURE   architecture (e.g. amd64)
  --bootloader {auto,chroot-grub2-device,chroot-grub2-drive,host-extlinux,host-grub2-device,host-grub2-drive,none}
                        approach to take during bootloader installation
                        (default: auto)
  --bootloader-force    apply more force when installing bootloader (default:
                        disabled)
  --hostname NAME       hostname to set (default: "machine")
  --openstack           prepare for use with OpenStack (default: disabled)
  --password PASSWORD   root password to set (default: password log-in
                        disabled)
  --password-file FILE  file to read root password from (default: password
                        log-in disabled)
  --resolv-conf FILE    file to copy nameserver entries from (default:
                        /etc/resolv.conf)
  --disk-id ID          specific disk identifier to apply, e.g. 0x12345678
  --first-partition-uuid UUID
                        specific UUID to apply to first partition, e.g.
                        c1b9d5a2-f162-11cf-9ece-0020afc76f16
  --machine-id ID       specific machine identifier to apply, e.g.
                        c1b9d5a2f16211cf9ece0020afc76f16

script integration:
  --scripts-pre DIRECTORY
                        scripts to run prior to chrooting phase, in
                        alphabetical order
  --scripts-chroot DIRECTORY
                        scripts to run during chrooting phase, in alphabetical
                        order
  --scripts-post DIRECTORY
                        scripts to run after chrooting phase, in alphabetical
                        order

command names:
  --grub2-install COMMAND
                        override grub2-install command

general configuration:
  --cache-dir DIRECTORY
                        directory to use for downloads (default:
                        /var/cache/directory-bootstrap/)

subcommands (choice of distribution):
  Run "image-bootstrap DISTRIBUTION --help" for details on options specific to that distribution.

  DISTRIBUTION          choice of distribution, pick from:
    arch                Arch Linux
    debian              Debian GNU/Linux
    gentoo              Gentoo
    ubuntu              Ubuntu

     _                          __             __      __
    (_)_ _  ___ ____ ____  ___ / /  ___  ___  / /____ / /________ ____
   / /  ' \/ _ `/ _ `/ -_)/__// _ \/ _ \/ _ \/ __(_-</ __/ __/ _ `/ _ \
  /_/_/_/_/\_,_/\_, /\__/    /_.__/\___/\___/\__/___/\__/_/  \_,_/ .__/
               /___/                      v2.0.0 :: 2020-02-28  /_/

Software libre licensed under AGPL v3 or later.
Brought to you by Sebastian Pipping <sebastian@pipping.org>.
Please report bugs at https://github.com/hartwork/image-bootstrap.  Thank you!
```

To show options specific to Debian, run ..

```console
# image-bootstrap debian --help
usage: image-bootstrap debian [-h] [--debootstrap COMMAND] [--release RELEASE]
                              [--mirror URL] [--debootstrap-opt OPTION]

optional arguments:
  -h, --help            show this help message and exit
  --release RELEASE     specify Debian release (default: stretch)
  --mirror URL          specify Debian mirror to use (e.g.
                        http://localhost:3142/debian for a local instance of
                        apt-cacher-ng; default:
                        http://httpredir.debian.org/debian)
  --debootstrap-opt OPTION
                        option to pass to debootstrap, in addition; can be
                        passed several times; use with --debootstrap-opt=...
                        syntax, i.e. with "="

command names:
  --debootstrap COMMAND
                        override debootstrap command
```


<a name="Piping"></a>
# Hints on using image-bootstrap within a pipe

If you want to run **image-bootstrap** in a pipe to capture its output to both
`stdout`/`stderr` to a single log file, be sure to run **image-bootstrap** in
unbuffered mode, e.g.:

```console
python3 -u image-bootstrap [OPTIONS] 2>&1 | tee my.log
```

The default shebang generated by python setuptools does not use `-u`. It's also
not easily possible to have it pass `-u` since the `env` command does allow for
for passing command parameters only in fairly recent versions. As a consequence,
`stdout`/`stderr` won't be synchronized and error output you see in a log file
will not exactly correspond to preceding/succeeding output on `stdout`. (See
[issue #71](https://github.com/hartwork/image-bootstrap/issues/71) for more details.)

Moreover, if you're using Bash and you need to keep track of
**image-bootstrap**'s exit code, be sure to run `set -o pipefail` prior to
invoking **image-bootstrap**.
(Please see the
[Pipelines](https://www.gnu.org/software/bash/manual/html_node/Pipelines.html)
section of the
[GNU Bash Reference Manual](https://www.gnu.org/software/bash/manual/html_node/index.html)
for more details.)


<a name="KnownLimitations"></a>
# Known limitations


<a name="PartitionBlockTarget"></a>
## Installing to partition block devices

Linux does not like partitions in partitions much.
It can be tricked using device mapper, though.

This is how to install to a partition using another partition as a temporary target.
The temporary target must

 * be 2 GiB in space or more (to hold the whole distribution) and

 * smaller or equal than the actualy target (for the later copy to work).

```console
# dmsetup create dm-linear-vda4 --table "0 $(blockdev --getsz /dev/vda4) linear /dev/vda4 0"
# image-bootstrap --openstack arch /dev/mapper/dm-linear-vda4
# partprobe /dev/mapper/dm-linear-vda4
# pv /dev/mapper/dm-linear-vda4p1 > /dev/vda2
# dmsetup remove dm-linear-vda4p1
# dmsetup remove dm-linear-vda4
```

(`/dev/vda2` is the real target, `/dev/vda4` the temporary one.)

There are other ways to achieve the same.
