"""Smoke tests for ui_ctk.WebsiteCopierCtk."""
import os
import sys
import unittest

os.environ.setdefault("INDEX_RIPPER_MODAL_DIALOGS", "0")
# 無頭環境
os.environ.setdefault("DISPLAY", ":99")

# Ensure Tcl/Tk can find its library when running under uv's isolated Python.
# TCL_LIBRARY must be set before _tkinter is first imported.
import sys as _sys
_tcl_dir = os.path.join(_sys.base_prefix, "lib", "tcl8.6")
if os.path.isdir(_tcl_dir) and "TCL_LIBRARY" not in os.environ:
    os.environ["TCL_LIBRARY"] = _tcl_dir


class TestWebsiteCopierCtkSmoke(unittest.TestCase):
    def _make_smoke(self):
        import importlib
        mod = importlib.import_module("ui_ctk")
        importlib.reload(mod)
        return mod.WebsiteCopierCtk(ui_smoke=True)

    def test_import(self):
        import ui_ctk  # noqa: F401

    def test_smoke_init_and_destroy(self):
        app = self._make_smoke()
        app.window.after(0, app.window.destroy)
        app.run()

    def test_has_url_var(self):
        app = self._make_smoke()
        app.window.after(0, app.window.destroy)
        app.run()
        self.assertTrue(hasattr(app, "url_var"))

    def test_has_log_text(self):
        app = self._make_smoke()
        app.window.after(0, app.window.destroy)
        app.run()
        self.assertTrue(hasattr(app, "log_text"))

    def test_full_ui_has_scan_btn(self):
        import ui_ctk, importlib
        importlib.reload(ui_ctk)
        app = ui_ctk.WebsiteCopierCtk(ui_smoke=False)
        app.window.after(0, app.window.destroy)
        app.run()
        self.assertTrue(hasattr(app, "scan_btn"))
        self.assertTrue(hasattr(app, "url_entry"))
        self.assertTrue(hasattr(app, "status_label"))


    def test_has_filters_container(self):
        import ui_ctk, importlib
        importlib.reload(ui_ctk)
        app = ui_ctk.WebsiteCopierCtk(ui_smoke=False)
        app.window.after(0, app.window.destroy)
        app.run()
        self.assertTrue(hasattr(app, "filters_container"))

    def test_add_file_type_filter(self):
        import ui_ctk, importlib
        importlib.reload(ui_ctk)
        app = ui_ctk.WebsiteCopierCtk(ui_smoke=False)
        app._add_file_type_filter(".mp4")
        app.window.after(0, app.window.destroy)
        app.run()
        self.assertIn(".mp4", app.file_types)
        self.assertIn(".mp4", app.file_type_widgets)


    def test_has_download_controls(self):
        import ui_ctk, importlib
        importlib.reload(ui_ctk)
        app = ui_ctk.WebsiteCopierCtk(ui_smoke=False)
        app.window.after(0, app.window.destroy)
        app.run()
        self.assertTrue(hasattr(app, "download_btn"))
        self.assertTrue(hasattr(app, "pause_btn"))
        self.assertTrue(hasattr(app, "threads_var"))
        self.assertTrue(hasattr(app, "toggle_panels_btn"))

    def test_has_treeview(self):
        import ui_ctk, importlib
        importlib.reload(ui_ctk)
        app = ui_ctk.WebsiteCopierCtk(ui_smoke=False)
        app.window.after(0, app.window.destroy)
        app.run()
        self.assertTrue(hasattr(app, "tree"))
        self.assertTrue(hasattr(app, "search_var"))

    def test_search_var_traces(self):
        import ui_ctk, importlib
        importlib.reload(ui_ctk)
        app = ui_ctk.WebsiteCopierCtk(ui_smoke=False)
        app.window.after(0, app.window.destroy)
        app.run()
        # search_var should have trace (on_search_filter_changed)
        self.assertTrue(len(app.search_var.trace_info()) > 0)

    def test_has_progress_bar(self):
        import ui_ctk, importlib
        importlib.reload(ui_ctk)
        app = ui_ctk.WebsiteCopierCtk(ui_smoke=False)
        app.window.after(0, app.window.destroy)
        app.run()
        self.assertTrue(hasattr(app, "progress_bar"))
        self.assertTrue(hasattr(app, "progress_label"))

    def test_has_panels_notebook(self):
        import ui_ctk, importlib
        importlib.reload(ui_ctk)
        app = ui_ctk.WebsiteCopierCtk(ui_smoke=False)
        app.window.after(0, app.window.destroy)
        app.run()
        self.assertTrue(hasattr(app, "panels_notebook"))
        self.assertIsNotNone(app.panels_notebook)
        self.assertTrue(hasattr(app, "log_text"))
        self.assertTrue(hasattr(app, "downloads_panel"))


    def test_poll_methods_exist(self):
        import ui_ctk, importlib
        importlib.reload(ui_ctk)
        app = ui_ctk.WebsiteCopierCtk(ui_smoke=True)
        for method in ("_poll_scan_queue", "_poll_file_queue",
                       "_flush_scan_buffer", "_schedule_flush"):
            self.assertTrue(hasattr(app, method), f"Missing: {method}")
        app.window.after(0, app.window.destroy)
        app.run()


if __name__ == "__main__":
    unittest.main()
