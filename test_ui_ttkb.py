import unittest

from ui_ttkb import should_skip_file_row


class TestUiTtkbScanEntryGate(unittest.TestCase):
    def test_should_not_skip_placeholder_none(self):
        self.assertFalse(should_skip_file_row(None))

    def test_should_skip_real_file_entry(self):
        self.assertTrue(should_skip_file_row({"url": "https://example.com/a.txt"}))

    def test_should_skip_only_for_real_entries_not_placeholders(self):
        placeholders = [None]
        real_entries = [{"url": "x"}, {"file_name": "a.txt"}]
        self.assertEqual([should_skip_file_row(v) for v in placeholders], [False])
        self.assertEqual([should_skip_file_row(v) for v in real_entries], [True, True])


if __name__ == "__main__":
    unittest.main()
