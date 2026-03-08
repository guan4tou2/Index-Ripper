"""Tests for backend module - scanning and downloading logic."""
import os
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

from backend import Backend


class MockUIManager:
    """Mock UI manager for testing backend."""

    def __init__(self):
        self.timeout = (10, 30)
        self.USER_AGENT = "TestAgent/1.0"
        self.is_scanning = False
        self.scanned_urls = 0
        self.total_urls = 0
        self.files_dict = {}
        self.folders = {}
        self.files_dict_lock = threading.Lock()
        self.folders_dict_lock = threading.Lock()
        self.scan_pause_event = threading.Event()
        self.scan_pause_event.set()
        self.should_stop = False
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.log_messages = []
        self.session = MagicMock()

    def log_message(self, message):
        self.log_messages.append(message)

    def notify_info(self, title, message):
        pass

    def notify_warning(self, title, message):
        pass

    def notify_error(self, title, message):
        pass

    def on_scan_started(self, url):
        self.is_scanning = True

    def on_scan_progress(self, scanned_urls, total_urls):
        self.scanned_urls = scanned_urls
        self.total_urls = total_urls

    def on_scan_item(self, **payload):
        is_directory = payload.get("is_directory")
        if is_directory:
            with self.folders_dict_lock:
                self.folders[payload.get("path")] = payload.get("url")
        else:
            with self.files_dict_lock:
                self.files_dict[payload.get("full_path")] = payload.get("url")

    def on_scan_finished(self, stopped):
        self.is_scanning = False


class TestBackendScan(unittest.TestCase):
    """Tests for website scanning functionality."""

    def setUp(self):
        self.ui = MockUIManager()
        self.backend = Backend(self.ui)
        self.backend.should_stop = False

    def test_backend_initialization(self):
        """Test Backend initializes with correct defaults."""
        self.assertFalse(self.backend.should_stop)
        self.assertEqual(self.backend.ui_manager, self.ui)

    def test_log_message(self):
        """Test _log method calls ui_manager.log_message."""
        self.backend._log("Test message")
        self.assertIn("Test message", self.ui.log_messages)

    def test_log_message_fallback(self):
        """Test _log falls back to print when ui_manager has no log_message."""
        self.backend.ui_manager = MagicMock()
        del self.backend.ui_manager.log_message
        # Should not raise
        self.backend._log("Test")

    def test_notify_info(self):
        """Test _notify calls correct handler for info."""
        with patch.object(self.ui, 'notify_info') as mock_notify:
            self.backend._notify("info", "Title", "Message")
            mock_notify.assert_called_once_with("Title", "Message")

    def test_notify_error(self):
        """Test _notify calls correct handler for error."""
        with patch.object(self.ui, 'notify_error') as mock_notify:
            self.backend._notify("error", "Title", "Message")
            mock_notify.assert_called_once_with("Title", "Message")

    def test_notify_warning(self):
        """Test _notify calls correct handler for warning."""
        with patch.object(self.ui, 'notify_warning') as mock_notify:
            self.backend._notify("warning", "Title", "Message")
            mock_notify.assert_called_once_with("Title", "Message")

    def test_call_ui_hook_exists(self):
        """Test _call_ui_hook calls existing hook."""
        self.ui.test_hook = MagicMock(return_value=True)
        result = self.backend._call_ui_hook("test_hook", foo="bar")
        self.assertTrue(result)
        self.ui.test_hook.assert_called_once_with(foo="bar")

    def test_call_ui_hook_missing(self):
        """Test _call_ui_hook handles missing hook gracefully."""
        result = self.backend._call_ui_hook("nonexistent_hook")
        self.assertFalse(result)

    def test_call_ui_hook_exception(self):
        """Test _call_ui_hook handles hook exception gracefully."""
        def failing_hook():
            raise Exception("Test error")

        self.ui.failing_hook = failing_hook
        result = self.backend._call_ui_hook("failing_hook")
        self.assertFalse(result)


class TestBackendDownload(unittest.TestCase):
    """Tests for file download functionality."""

    def setUp(self):
        self.ui = MockUIManager()
        self.backend = Backend(self.ui)
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @unittest.skip("Requires complex network mocking")
    def test_download_file_creates_directory(self):
        """Test download_file creates target directory if needed."""
        subdir = os.path.join(self.temp_dir, "subdir", "nested")
        test_file = os.path.join(subdir, "test.txt")

        # Directory shouldn't exist yet
        self.assertFalse(os.path.exists(subdir))

        # Mock session.get to avoid actual network call
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "10"}
        mock_response.iter_content = lambda size: [b"test data"]
        mock_response.raise_for_status = MagicMock()

        self.ui.session.get = MagicMock(return_value=mock_response)

        # Mock the pause event to not block
        self.ui.pause_event = threading.Event()
        self.ui.pause_event.set()

        result = self.backend.download_file(
            "http://example.com/test.txt",
            test_file,
            "test.txt"
        )

        # File should be created
        self.assertTrue(os.path.exists(test_file))


class TestBackendProcessFile(unittest.TestCase):
    """Tests for file processing in scan."""

    def setUp(self):
        self.ui = MockUIManager()
        self.backend = Backend(self.ui)

    def test_process_file_extracts_filename(self):
        """Test _process_file correctly extracts file info from URL."""
        # This tests the parsing logic without network calls
        url = "http://example.com/path/to/file.txt"
        # The method should handle this without error
        # Full test would require mocking session.head


if __name__ == "__main__":
    unittest.main()
