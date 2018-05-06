from unittest import TestCase

from image_bootstrap.mount import MountFinder


class TestMountInfoParser(TestCase):

    def test_line_parsing(self):
        for mount_info_line, expected_mount in (
                ('17 21 0:4 / /proc rw,nosuid,nodev,noexec,relatime shared:12 - proc proc rw', '/proc'),
                ('314 20 0:3 net:[4026532205] /run/docker/netns/8546120315b2 rw shared:124 - nsfs nsfs rw', '/run/docker/netns/8546120315b2'),
                ):
            finder = MountFinder()
            groupdict = finder._parse_line(mount_info_line)
            assert groupdict['mount'] == expected_mount

    def test_loading(self):
        finder = MountFinder()
        finder.load()
