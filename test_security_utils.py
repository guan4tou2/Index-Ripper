import os
import tempfile
import unittest

from app_utils import (
    is_url_in_scope,
    safe_join,
    sanitize_filename,
    sanitize_path_segment,
)


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
