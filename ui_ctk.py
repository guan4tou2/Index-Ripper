from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import customtkinter as ctk

from app_utils import default_download_folder, normalize_extension, safe_join, sanitize_filename
from backend import Backend
from ui_downloads import DownloadsPanel
from ui_theme import (
    apply_app_theme,
    configure_action_button_styles,
    ui_tokens,
)


def should_skip_file_row(existing_entry) -> bool:
    """Return True when a file row is already fully registered."""
    return existing_entry is not None


class WebsiteCopierCtk:
    USER_AGENT = "IndexRipper/2.0"

    def __init__(self, ui_smoke: bool = False):
        self._ui_smoke = bool(ui_smoke)
        self.debug_enabled = os.environ.get("INDEX_RIPPER_DEBUG", "0") != "0"
        self.use_modal_dialogs = os.environ.get("INDEX_RIPPER_MODAL_DIALOGS", "0") == "1"

        apply_app_theme(ctk)

        self.window = ctk.CTk()
        self.window.title("Index Ripper")
        self.window.geometry("1200x900")
        self.window.minsize(900, 650)

        configure_action_button_styles(self.window, ctk, ttk)

        self.ui_tokens = ui_tokens()

        self.backend = Backend(self)

        self.pause_event = threading.Event()
        self.pause_event.set()
        self.scan_pause_event = threading.Event()
        self.scan_pause_event.set()

        self.is_scanning = False
        self.scanned_urls = 0
        self.total_urls = 0

        self.files_dict_lock = threading.Lock()
        self.folders_dict_lock = threading.Lock()
        self.files_dict: dict[str, dict] = {}
        self.folders: dict[str, str] = {}
        self.checked_items: set[str] = set()
        self.checkbox_checked = "✔ "

        self.dir_queue = Queue()
        self.file_queue = Queue()
        self.scan_item_buffer = Queue()
        self.is_processing_dirs = False
        self.is_processing_files = False
        self.scan_flush_interval_ms = 16
        self.scan_flush_batch_size = 200
        self.scan_flush_job = None
        self._last_logged_queue_size = None

        self.file_types: dict[str, tk.BooleanVar] = {}
        self.file_type_counts: dict[str, int] = {}
        self.file_type_widgets: dict = {}

        self.download_path = ""
        self.download_queue = Queue()
        self.max_workers = 5
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.active_downloads = []

        retry_strategy = Retry(
            total=3,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 504],
        )
        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.timeout = (10, 20)

        self._build_ui()

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        if not self._ui_smoke:
            self.window.bind("<Control-f>", self.focus_search)
            self.window.bind("<Control-l>", self.focus_logs)
            self.window.bind("<Escape>", self.clear_search)
            self.window.bind_all("<Command-v>", self._on_global_url_paste, add="+")
            self.window.bind_all("<Command-V>", self._on_global_url_paste, add="+")
            self.window.bind_all("<Control-v>", self._on_global_url_paste, add="+")
            self.window.bind_all("<Control-V>", self._on_global_url_paste, add="+")
            self.window.bind_all("<<Paste>>", self._on_global_url_paste, add="+")

    def _build_ui(self) -> None:
        if self._ui_smoke:
            self._build_ui_smoke_only()
        else:
            self._build_full_ui()

    def _build_ui_smoke_only(self) -> None:
        self.url_var = tk.StringVar(value="https://example.com/")
        self.search_var = tk.StringVar()
        self.log_text = ctk.CTkTextbox(self.window, height=80)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_text.insert("end", "UI smoke minimal view initialized.\n")
        self.panels_notebook = None
        self.logs_tab = None

    def _build_full_ui(self) -> None:
        pass

    def run(self) -> None:
        self.window.mainloop()

    def on_closing(self) -> None:
        self.executor.shutdown(wait=False)
        self.window.destroy()

    def log_message(self, message: str) -> None:
        try:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
        except Exception:
            pass

    def _debug(self, message: str) -> None:
        if self.debug_enabled:
            print(f"[DEBUG] {message}")
            try:
                self.log_text.configure(state="normal")
                self.log_text.insert("end", f"[DEBUG] {message}\n")
                self.log_text.see("end")
            except Exception:
                pass

    def notify_info(self, title: str, message: str) -> None:
        if self.use_modal_dialogs:
            messagebox.showinfo(title, message)
        else:
            self.log_message(f"[INFO] {title}: {message}")

    def notify_warning(self, title: str, message: str) -> None:
        if self.use_modal_dialogs:
            messagebox.showwarning(title, message)
        else:
            self.log_message(f"[WARNING] {title}: {message}")

    def notify_error(self, title: str, message: str) -> None:
        if self.use_modal_dialogs:
            messagebox.showerror(title, message)
        else:
            self.log_message(f"[ERROR] {title}: {message}")

    # --- Stub methods (implemented in later Tasks) ---

    def _build_filters_row(self) -> None:
        pass

    def _build_treeview(self) -> None:
        pass

    def _build_progress_section(self) -> None:
        pass

    def _build_panels(self) -> None:
        pass

    def _build_download_controls(self) -> None:
        pass

    def focus_search(self, event=None) -> None:
        pass

    def focus_logs(self, event=None) -> None:
        pass

    def clear_search(self, event=None) -> None:
        pass

    def _on_global_url_paste(self, event=None) -> None:
        pass
