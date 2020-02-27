import unittest

from ..executor import _sanitize_path


class PathExtensionTest(unittest.TestCase):

    def test_path_extension__arch_root(self):
        original_path = '/usr/local/sbin:/usr/local/bin:/usr/bin'
        expected_path = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'

        self.assertEqual(_sanitize_path(original_path), expected_path)

    def test_path_extension__debian_jessie_stretch_root(self):
        original_path = '/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin:.'
        expected_path = original_path

        self.assertEqual(_sanitize_path(original_path), expected_path)

    def test_path_extension__stretch_unprivileged(self):
        original_path = '/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games'
        expected_path = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/games:/usr/games'

        self.assertEqual(_sanitize_path(original_path), expected_path)

    def test_path_extension__disjoint(self):
        original_path = '/one:/two'
        expected_path = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/one:/two'

        self.assertEqual(_sanitize_path(original_path), expected_path)
