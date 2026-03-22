import os
import tempfile
import unittest

from index_ripper.utils import (
    default_download_folder,
    is_url_in_scope,
    normalize_extension,
    safe_join,
    sanitize_filename,
    sanitize_path_segment,
    shorten_path,
)


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


class TestSecurityUtils(unittest.TestCase):
    def test_sanitize_path_segment_blocks_traversal_patterns(self):
        self.assertEqual(sanitize_path_segment(".."), "_")
        self.assertEqual(sanitize_path_segment("a/b"), "a_b")
        self.assertEqual(sanitize_path_segment(r"a\b"), "a_b")
        self.assertEqual(sanitize_path_segment("%2e%2e"), "_")

    def test_sanitize_path_segment_windows_illegal_chars(self):
        self.assertEqual(sanitize_path_segment('<>:"/\\|?*'), "_________")

    def test_sanitize_filename_reuses_segment_rules(self):
        self.assertEqual(sanitize_filename(" report. "), "report")

    def test_is_url_in_scope_respects_path_boundary(self):
        base = "https://example.com/a/b/"
        self.assertTrue(is_url_in_scope(base, "https://example.com/a/b/file.txt"))
        self.assertTrue(is_url_in_scope(base, "https://example.com/a/b/"))
        self.assertFalse(is_url_in_scope(base, "https://example.com/a/bad/file.txt"))

    def test_is_url_in_scope_checks_origin(self):
        base = "https://example.com/a/b/"
        self.assertFalse(is_url_in_scope(base, "http://example.com/a/b/file.txt"))
        self.assertFalse(is_url_in_scope(base, "https://evil.com/a/b/file.txt"))

    def test_safe_join_rejects_escape(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError):
                safe_join(tmpdir, ["..", "outside.txt"])

    def test_safe_join_accepts_normal_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = safe_join(tmpdir, ["folder", "file.txt"])
            self.assertTrue(out.startswith(os.path.realpath(tmpdir)))


if __name__ == "__main__":
    unittest.main()
