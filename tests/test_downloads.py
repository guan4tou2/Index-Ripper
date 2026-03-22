import unittest

from index_ripper.ui import downloads


class TestUIDownloadsSemantics(unittest.TestCase):
    def test_download_status_state_mapping(self):
        self.assertEqual(downloads.download_status_state("Queued"), "queued")
        self.assertEqual(downloads.download_status_state("Downloading 12.0%"), "active")
        self.assertEqual(downloads.download_status_state("Completed"), "success")
        self.assertEqual(downloads.download_status_state("Failed"), "error")
        self.assertEqual(downloads.download_status_state("Canceling..."), "warning")
        self.assertEqual(downloads.download_status_state("something else"), "queued")


if __name__ == "__main__":
    unittest.main()
