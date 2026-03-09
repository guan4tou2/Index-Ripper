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


if __name__ == "__main__":
    unittest.main()
