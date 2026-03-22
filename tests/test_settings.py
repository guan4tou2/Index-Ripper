import os
import tempfile
import unittest

from index_ripper.settings import load_settings, save_settings


class TestSettingsStore(unittest.TestCase):
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "settings.json")
            save_settings(path, {"a": 1, "b": "x"})
            self.assertEqual(load_settings(path), {"a": 1, "b": "x"})

    def test_load_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "missing.json")
            self.assertEqual(load_settings(path), {})

    def test_load_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "bad.json")
            with open(path, "w", encoding="utf-8") as file_obj:
                file_obj.write("{bad")
            self.assertEqual(load_settings(path), {})


if __name__ == "__main__":
    unittest.main()
