import unittest

import ui_downloads


class TestUIDownloadsSemantics(unittest.TestCase):
    def test_download_status_state_mapping(self):
        self.assertEqual(ui_downloads.download_status_state("Queued"), "queued")
        self.assertEqual(ui_downloads.download_status_state("Downloading 12.0%"), "active")
        self.assertEqual(ui_downloads.download_status_state("Completed"), "success")
        self.assertEqual(ui_downloads.download_status_state("Failed"), "error")
        self.assertEqual(ui_downloads.download_status_state("Canceling..."), "warning")
        self.assertEqual(ui_downloads.download_status_state("something else"), "queued")


if __name__ == "__main__":
    unittest.main()
