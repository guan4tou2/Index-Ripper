import unittest

from app_utils import default_download_folder, normalize_extension, shorten_path


class TestAppUtils(unittest.TestCase):
    def test_normalize_extension_normal(self):
        self.assertEqual(normalize_extension("a.TXT"), ".txt")

    def test_normalize_extension_none(self):
        self.assertEqual(normalize_extension("README"), ".(No Extension)")

    def test_shorten_path(self):
        self.assertEqual(shorten_path("/a/b", keep=10), "/a/b")
        self.assertEqual(shorten_path("/" + "x" * 50, keep=10), "..." + "x" * 10)

    def test_default_download_folder(self):
        out = default_download_folder("https://example.com/a/b", "/tmp")
        self.assertTrue(out.endswith("example.com"))


if __name__ == "__main__":
    unittest.main()
