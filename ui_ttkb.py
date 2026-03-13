from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue

import tkinter as tk
from tkinter import filedialog, messagebox

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import ttkbootstrap as ttkb
from ttkbootstrap.constants import BOTH, END, LEFT, RIGHT, TOP, X, Y

from app_utils import default_download_folder, normalize_extension, safe_join, sanitize_filename
from backend import Backend


def should_skip_file_row(existing_entry) -> bool:
    """Return True when a file row is already fully registered."""
    return existing_entry is not None


class WebsiteCopierTtkb:
    USER_AGENT = "IndexRipper/2.0"

    def __init__(self, ui_smoke: bool = False):
        self._ui_smoke = bool(ui_smoke)
        self.debug_enabled = os.environ.get("INDEX_RIPPER_DEBUG", "0") != "0"
        self.use_modal_dialogs = os.environ.get("INDEX_RIPPER_MODAL_DIALOGS", "0") == "1"

        self.window = ttkb.Window(title="Index Ripper", themename="flatly")
        self.window.geometry("1200x900")
        self.window.minsize(900, 650)

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
        self.file_type_widgets: dict[str, tk.Checkbutton] = {}

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
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10,
            pool_block=False,
        )
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
        self._debug("WebsiteCopierTtkb initialized")

    def _build_ui(self) -> None:
        if self._ui_smoke:
            self._build_ui_smoke_only()
            return

        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(2, weight=1)

        header = ttkb.Frame(self.window, padding=10)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        ttkb.Label(header, text="URL").grid(row=0, column=0, sticky="w")
        self.url_var = tk.StringVar()
        self.url_entry = tk.Entry(header, textvariable=self.url_var, relief="flat")
        self.url_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        self.url_entry.bind("<Command-v>", self._on_url_paste)
        self.url_entry.bind("<Command-V>", self._on_url_paste)
        self.url_entry.bind("<Control-v>", self._on_url_paste)
        self.url_entry.bind("<Control-V>", self._on_url_paste)
        self.url_entry.bind("<Shift-Insert>", self._on_url_paste)
        self.url_entry.bind("<Button-2>", self._show_url_context_menu)
        self.url_entry.bind("<Button-3>", self._show_url_context_menu)

        self.url_context_menu = tk.Menu(self.window, tearoff=0)
        self.url_context_menu.add_command(label="Paste", command=self._paste_into_url_entry)

        self.status_label = ttkb.Label(header, text="Ready", bootstyle="success")
        self.status_label.grid(row=0, column=2, sticky="e", padx=(0, 8))

        actions = ttkb.Frame(header)
        actions.grid(row=0, column=3, sticky="e")
        self.scan_btn = ttkb.Button(actions, text="Scan", bootstyle="primary", command=self.start_scan)
        self.scan_btn.pack(side=LEFT, padx=3)
        self.scan_pause_btn = ttkb.Button(
            actions,
            text="Pause Scan",
            bootstyle="secondary",
            command=self.toggle_scan_pause,
            state="disabled",
        )
        self.scan_pause_btn.pack(side=LEFT, padx=3)
        self.clear_scan_btn = ttkb.Button(actions, text="Clear", command=self.clear_scan_results)
        self.clear_scan_btn.pack(side=LEFT, padx=3)

        filters_and_controls = ttkb.Frame(self.window, padding=(10, 0, 10, 6))
        filters_and_controls.grid(row=1, column=0, sticky="ew")
        filters_and_controls.columnconfigure(0, weight=1)
        filters_and_controls.columnconfigure(1, weight=0)

        self.filters_frame = ttkb.Frame(filters_and_controls)
        self.filters_frame.grid(row=0, column=0, sticky="ew")
        self.filters_frame.columnconfigure(0, weight=1)
        self.filters_canvas, self.filters_container = self._create_scrollable_container(
            self.filters_frame,
            height=85,
        )
        type_actions = ttkb.Frame(self.filters_frame)
        type_actions.pack(fill=X, pady=(4, 0))
        ttkb.Button(
            type_actions,
            text="Select All Types",
            bootstyle="secondary-outline",
            command=self.select_all_types,
        ).pack(side=LEFT, padx=(0, 6))
        ttkb.Button(
            type_actions,
            text="Deselect All Types",
            bootstyle="secondary-outline",
            command=self.deselect_all_types,
        ).pack(side=LEFT)

        controls = ttkb.Frame(filters_and_controls)
        controls.grid(row=0, column=1, sticky="e", padx=(10, 0))
        self.download_btn = ttkb.Button(
            controls,
            text="Download Selected",
            bootstyle="success",
            command=self.download_selected,
        )
        self.download_btn.grid(row=0, column=0, padx=4)
        self.pause_btn = ttkb.Button(
            controls,
            text="Pause",
            bootstyle="secondary",
            command=self.toggle_pause,
            state="disabled",
        )
        self.pause_btn.grid(row=0, column=1, padx=4)
        self.path_btn = ttkb.Button(
            controls,
            text="Choose Folder",
            bootstyle="secondary",
            command=self.choose_download_path,
        )
        self.path_btn.grid(row=0, column=2, padx=4)
        self.panels_visible = True
        self.toggle_panels_btn = ttkb.Button(
            controls,
            text="Hide Panels",
            bootstyle="secondary-outline",
            command=self.toggle_panels,
        )
        self.toggle_panels_btn.grid(row=0, column=5, padx=(10, 0))

        ttkb.Label(controls, text="Threads").grid(row=0, column=3, padx=(12, 4))
        self.threads_var = tk.StringVar(value="5")
        try:
            self.threads_combo = ttkb.Combobox(
                controls,
                values=[str(i) for i in range(1, 11)],
                textvariable=self.threads_var,
                width=4,
                state="readonly",
            )
            self.threads_combo.bind("<<ComboboxSelected>>", self.update_thread_count)
        except (tk.TclError, TypeError):
            # Fallback when ttkbootstrap arrow assets fail to initialize.
            self.threads_combo = tk.Spinbox(
                controls,
                from_=1,
                to=10,
                textvariable=self.threads_var,
                width=4,
                command=self.update_thread_count,
                relief="flat",
            )
            self.threads_combo.bind("<Return>", self.update_thread_count)
            self.threads_combo.bind("<FocusOut>", self.update_thread_count)
        self.threads_combo.grid(row=0, column=4)

        self.tree_frame = ttkb.Frame(self.window, padding=(10, 0, 10, 8))
        self.tree_frame.grid(row=2, column=0, sticky="nsew")
        self.tree_frame.columnconfigure(0, weight=1)
        self.tree_frame.rowconfigure(1, weight=1)

        search_bar = ttkb.Frame(self.tree_frame)
        search_bar.grid(row=0, column=0, sticky="ew")
        search_bar.columnconfigure(1, weight=1)
        ttkb.Label(search_bar, text="Search").grid(row=0, column=0, padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_entry = ttkb.Entry(search_bar, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, sticky="ew")
        self.search_var.trace_add("write", self.on_search_filter_changed)

        self.tree = ttkb.Treeview(
            self.tree_frame,
            columns=("size", "type", "full_path"),
            show="tree headings",
            bootstyle="info",
            selectmode="extended",
        )
        self.tree.heading("#0", text="Path", command=lambda: self.sort_tree("#0"))
        self.tree.heading("size", text="Size", command=lambda: self.sort_tree("size"))
        self.tree.heading("type", text="Type", command=lambda: self.sort_tree("type"))
        self.tree.column("#0", width=600, stretch=True)
        self.tree.column("size", width=120, stretch=False, anchor="e")
        self.tree.column("type", width=240, stretch=False)
        self.tree.column("full_path", width=0, stretch=False, anchor="w")
        self.tree.grid(row=1, column=0, sticky="nsew")
        style = ttkb.Style()
        style.configure("Treeview", font=("SF Pro Text", 14), rowheight=34)
        style.configure("Treeview.Heading", font=("SF Pro Text", 13, "bold"))
        self.tree.tag_configure("checked", foreground="#0F766E")
        self.tree.bind("<Command-a>", self._on_tree_select_all)
        self.tree.bind("<Control-a>", self._on_tree_select_all)
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Button-2>", self.show_context_menu)
        self.tree.bind("<Control-Button-1>", self.show_context_menu)
        self.tree.bind("<B1-Motion>", self.on_tree_drag_select)
        self.tree.bind("<space>", self.on_tree_space)
        self.tree.bind("<Return>", self.on_tree_enter)

        self.tree_scroll = tk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.tree_scroll.set)
        self.tree_scroll.grid(row=1, column=1, sticky="ns")

        self.progress_frame = ttkb.Frame(self.window, padding=(10, 0, 10, 8))
        self.progress_frame.grid(row=3, column=0, sticky="ew")
        self.progress_frame.columnconfigure(0, weight=1)
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttkb.Progressbar(
            self.progress_frame,
            variable=self.progress_var,
            maximum=100,
            bootstyle="success",
        )
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        self.progress_label = ttkb.Label(self.progress_frame, text="")
        self.progress_label.grid(row=1, column=0, sticky="w")

        self.panels_notebook = ttkb.Notebook(self.window, bootstyle="secondary")
        self.panels_notebook.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.downloads_tab = ttkb.Frame(self.panels_notebook, padding=10)
        self.logs_tab = ttkb.Frame(self.panels_notebook, padding=10)
        self.panels_notebook.add(self.downloads_tab, text="Downloads")
        self.panels_notebook.add(self.logs_tab, text="Logs")
        self.panels_notebook.select(self.logs_tab)

        downloads_frame = ttkb.Frame(self.downloads_tab)
        downloads_frame.pack(fill=X)
        self.downloads_canvas, self.downloads_container = self._create_scrollable_container(
            downloads_frame,
            height=140,
        )

        logs_wrap = ttkb.Frame(self.logs_tab)
        logs_wrap.pack(fill=X)
        self.log_text = tk.Text(logs_wrap, height=8, wrap="word")
        self.log_text.pack(side=LEFT, fill=X, expand=True)
        self.log_scroll = tk.Scrollbar(logs_wrap, orient="vertical", command=self.log_text.yview)
        self.log_scroll.pack(side=RIGHT, fill=Y)
        self.log_text.configure(yscrollcommand=self.log_scroll.set)

        self.download_items: dict[str, dict] = {}
        self.sort_reverse = False
        self.full_tree_backup = {}
        self.drag_anchor_item = ""
        self.context_menu = tk.Menu(self.window, tearoff=0)
        self.context_menu.add_command(label="Select All", command=self.select_all)
        self.context_menu.add_command(label="Deselect All", command=self.deselect_all)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Expand All", command=self.expand_all)
        self.context_menu.add_command(label="Collapse All", command=self.collapse_all)

    def _build_ui_smoke_only(self) -> None:
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=1)

        header = tk.Frame(self.window)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        tk.Label(header, text="Index Ripper ttkbootstrap UI Smoke").pack(anchor="w")

        self.url_var = tk.StringVar(value="https://example.com/")
        tk.Entry(header, textvariable=self.url_var).pack(fill=X, pady=(6, 0))

        body = tk.Frame(self.window)
        body.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(body, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=0, sticky="ew")

        self.log_text = tk.Text(body, height=8, wrap="word")
        self.log_text.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.log_text.insert("end", "UI smoke minimal view initialized.\n")

        self.panels_notebook = None
        self.logs_tab = None

    def notify_info(self, title: str, message: str) -> None:
        if not self.use_modal_dialogs:
            self.log_message(f"[INFO] {title}: {message}")
            return
        try:
            messagebox.showinfo(title, message)
        except Exception:
            self.log_message(f"[INFO] {title}: {message}")

    def notify_warning(self, title: str, message: str) -> None:
        if not self.use_modal_dialogs:
            self.log_message(f"[WARN] {title}: {message}")
            return
        try:
            messagebox.showwarning(title, message)
        except Exception:
            self.log_message(f"[WARN] {title}: {message}")

    def notify_error(self, title: str, message: str) -> None:
        if not self.use_modal_dialogs:
            self.log_message(f"[ERROR] {title}: {message}")
            return
        try:
            messagebox.showerror(title, message)
        except Exception:
            self.log_message(f"[ERROR] {title}: {message}")

    def log_message(self, message: str) -> None:
        try:
            self.log_text.insert(END, message + "\n")
            self.log_text.see(END)
        except tk.TclError:
            pass

    def _debug(self, message: str) -> None:
        if not self.debug_enabled:
            return
        line = f"[DEBUG] {message}"
        try:
            print(line)
        except Exception:
            pass
        try:
            if hasattr(self, "log_text"):
                self.log_text.insert(END, line + "\n")
                self.log_text.see(END)
        except Exception:
            pass

    def _set_status(self, text: str, style: str = "secondary") -> None:
        try:
            self.status_label.configure(text=text, bootstyle=style)
        except tk.TclError:
            pass

    def choose_download_path(self) -> None:
        path = filedialog.askdirectory(title="Choose Download Location")
        if path:
            self.download_path = path

    def _on_url_paste(self, _event=None):
        """Paste clipboard into URL field exactly once."""
        self._debug("URL paste handler invoked")
        self._paste_into_url_entry()
        return "break"

    def _on_global_url_paste(self, _event=None):
        try:
            focused = self.window.focus_get()
        except tk.TclError:
            return None
        if focused is self.url_entry:
            self._debug("Global paste routed to URL entry")
            self._paste_into_url_entry()
            return "break"
        return None

    def _paste_into_url_entry(self):
        try:
            text = self.window.clipboard_get()
        except tk.TclError:
            return
        if not text:
            return
        try:
            if self.url_entry.selection_present():
                self.url_entry.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        self.url_entry.insert("insert", text)
        self._debug(f"Pasted URL text length={len(text)}")

    def _show_url_context_menu(self, event):
        try:
            self.url_entry.focus_set()
            self.url_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.url_context_menu.grab_release()
        return "break"

    def update_thread_count(self, _event=None) -> None:
        try:
            self.max_workers = max(1, min(10, int(self.threads_var.get())))
        except ValueError:
            self.max_workers = 5
        self.threads_var.set(str(self.max_workers))
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

    def toggle_pause(self) -> None:
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_btn.configure(text="Resume")
            self.progress_label.configure(text="Downloads paused")
        else:
            self.pause_event.set()
            self.pause_btn.configure(text="Pause")

    def toggle_scan_pause(self) -> None:
        if self.scan_pause_event.is_set():
            self.scan_pause_event.clear()
            self.scan_pause_btn.configure(text="Resume Scan")
            self._set_status("Scan Paused", "warning")
        else:
            self.scan_pause_event.set()
            self.scan_pause_btn.configure(text="Pause Scan")
            self._set_status("Scanning", "info")

    def _run_on_ui_thread(self, callback, *args, wait: bool = False):
        if not wait:
            self.window.after(0, lambda: callback(*args))
            return
        done = threading.Event()
        error_box = {}

        def wrapped():
            try:
                callback(*args)
            except Exception as ex:
                error_box["error"] = ex
            finally:
                done.set()

        self.window.after(0, wrapped)
        done.wait()
        if "error" in error_box:
            raise error_box["error"]

    def _create_scrollable_container(self, parent, height: int):
        canvas = tk.Canvas(parent, height=height, highlightthickness=0, borderwidth=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        container = ttkb.Frame(canvas)

        window_id = canvas.create_window((0, 0), window=container, anchor="nw")

        def _on_container_configure(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfigure(window_id, width=event.width)

        container.bind("<Configure>", _on_container_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=LEFT, fill=X, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        return canvas, container

    def on_scan_started(self, url):
        self._run_on_ui_thread(self._on_scan_started_ui, url, wait=True)

    def _on_scan_started_ui(self, _url):
        self.is_scanning = True
        self.scanned_urls = 0
        self.total_urls = 0
        self.scan_pause_btn.configure(state="normal", text="Pause Scan")
        self.scan_btn.configure(text="Stop Scan")
        self._set_status("Scanning", "info")

        self._cancel_scan_item_flush()
        while not self.scan_item_buffer.empty():
            self.scan_item_buffer.get()
        while not self.dir_queue.empty():
            self.dir_queue.get()
        while not self.file_queue.empty():
            self.file_queue.get()
        self.is_processing_dirs = False
        self.is_processing_files = False

        with self.files_dict_lock:
            self.files_dict.clear()
        with self.folders_dict_lock:
            self.folders.clear()

        for item in self.tree.get_children(""):
            self.tree.delete(item)
        self.checked_items.clear()

        self.file_types.clear()
        self.file_type_counts.clear()
        for widget in self.filters_container.winfo_children():
            widget.destroy()

        self.progress_var.set(0)
        self.progress_label.configure(text="Preparing...")

    def on_scan_progress(self, scanned_urls, total_urls):
        self._run_on_ui_thread(self._on_scan_progress_ui, scanned_urls, total_urls)

    def _on_scan_progress_ui(self, scanned_urls, total_urls):
        self.scanned_urls = scanned_urls
        self.total_urls = total_urls
        self.update_scan_progress()

    def on_scan_item(self, **payload):
        self._run_on_ui_thread(self._on_scan_item_ui, payload)

    def _on_scan_item_ui(self, payload: dict):
        self.scan_item_buffer.put(
            (
                bool(payload.get("is_directory")),
                payload.get("path"),
                payload.get("url"),
                payload.get("file_name"),
                payload.get("size"),
                payload.get("file_type"),
                payload.get("full_path"),
            )
        )
        self._schedule_scan_item_flush()

    def _schedule_scan_item_flush(self):
        if self.scan_flush_job is not None:
            return
        if not self.is_scanning and self.scan_item_buffer.empty():
            return
        self.scan_flush_job = self.window.after(
            self.scan_flush_interval_ms, self._flush_scan_item_buffer
        )

    def _cancel_scan_item_flush(self):
        if self.scan_flush_job is None:
            return
        try:
            self.window.after_cancel(self.scan_flush_job)
        except tk.TclError:
            pass
        finally:
            self.scan_flush_job = None

    def _flush_scan_item_buffer(self, max_items=None, reschedule=True):
        self.scan_flush_job = None
        if max_items is None:
            max_items = self.scan_flush_batch_size

        processed = 0
        added_dir = False
        added_file = False

        while processed < max_items:
            try:
                (
                    is_directory,
                    path,
                    url,
                    file_name,
                    size,
                    file_type,
                    full_path,
                ) = self.scan_item_buffer.get_nowait()
            except Empty:
                break

            if is_directory:
                with self.folders_dict_lock:
                    self.dir_queue.put((path, url))
                added_dir = True
            else:
                self.file_queue.put((path, url, file_name, size, file_type, full_path))
                added_file = True
            processed += 1

        if added_dir and not self.is_processing_dirs:
            self.window.after(0, self.process_dir_queue)
        if added_file and not self.is_processing_files:
            self.window.after(0, self.process_file_queue)

        if reschedule and not self.scan_item_buffer.empty():
            self._schedule_scan_item_flush()

    def on_scan_finished(self, stopped):
        self._run_on_ui_thread(self._on_scan_finished_ui, stopped)

    def _on_scan_finished_ui(self, stopped):
        self.is_scanning = False
        self._cancel_scan_item_flush()
        while not self.scan_item_buffer.empty():
            self._flush_scan_item_buffer(max_items=self.scan_flush_batch_size, reschedule=False)
        while not self.dir_queue.empty():
            self.process_dir_queue()
        while not self.file_queue.empty():
            self.process_file_queue()

        self.scan_btn.configure(text="Scan")
        self.scan_pause_btn.configure(state="disabled", text="Pause Scan")
        self.scan_pause_event.set()

        if stopped:
            self.progress_label.configure(text="Scan stopped.")
            self._set_status("Ready", "success")
            self.log_message("[Scan] Stopped by user.")
        else:
            self.progress_label.configure(text="Scan finished.")
            self._set_status("Ready", "success")
            self.log_message("[Scan] Finished.")
        self.scan_completed()
        tree_items = len(self._all_tree_items())
        with self.files_dict_lock:
            file_entries = len(self.files_dict)
        self._debug(
            f"scan_finished stopped={stopped} files_dict={file_entries} tree_items={tree_items}"
        )

    def update_scan_progress(self):
        if self.total_urls <= 0:
            self.progress_var.set(0)
            return
        pct = (self.scanned_urls / self.total_urls) * 100
        self.progress_var.set(pct)
        self.progress_label.configure(text=f"Scan: {self.scanned_urls}/{self.total_urls}")

    def scan_completed(self):
        self.full_tree_backup.clear()
        self._backup_full_tree()

    def create_folder_structure(self, dir_path: str, url: str) -> str:
        if not dir_path:
            dir_path = "/"
        parts = [p for p in dir_path.split("/") if p]

        current = ""
        parent_id = ""
        for part in parts:
            current = current + "/" + part
            with self.folders_dict_lock:
                existing = self.folders.get(current)
            if existing:
                parent_id = existing
                continue

            node_id = self.tree.insert(
                parent_id,
                "end",
                text=f"📁 {part}",
                values=("", "dir", ""),
                tags=("folder",),
                open=True,
            )
            with self.folders_dict_lock:
                self.folders[current] = node_id
            parent_id = node_id

        return parent_id

    def process_dir_queue(self):
        try:
            self.is_processing_dirs = True
            if not self.dir_queue.empty():
                dir_path, url = self.dir_queue.get()
                self.create_folder_structure(dir_path, url)
                self.window.after(10, self.process_dir_queue)
            else:
                self.is_processing_dirs = False
        except tk.TclError:
            self.is_processing_dirs = False

    def process_file_queue(self):
        try:
            self.is_processing_files = True
            qsize = self.file_queue.qsize()
            if qsize != self._last_logged_queue_size and (qsize <= 5 or qsize % 100 == 0):
                self._debug(f"process_file_queue queue_size={qsize}")
                self._last_logged_queue_size = qsize
            if not self.file_queue.empty():
                (
                    dir_path,
                    url,
                    file_name,
                    size,
                    file_type,
                    full_path,
                ) = self.file_queue.get()
                self.update_file_types(file_name)
                self._add_file_to_tree(dir_path, url, file_name, size, file_type, full_path)
                self.window.after(5, self.process_file_queue)
            else:
                self.is_processing_files = False
        except tk.TclError:
            self.is_processing_files = False

    def _add_file_to_tree(self, dir_path, url, file_name, size, file_type, full_path, from_cache=False):
        if not file_name:
            return
        is_html_dir_like = (
            isinstance(file_type, str)
            and "text/html" in file_type.lower()
            and "." not in (file_name or "")
        )
        parent_id = self.create_folder_structure(dir_path, url)
        if not from_cache:
            with self.files_dict_lock:
                existing_entry = self.files_dict.get(full_path)
                if should_skip_file_row(existing_entry):
                    return
                if is_html_dir_like:
                    self.files_dict.pop(full_path, None)
                else:
                    self.files_dict[full_path] = {
                        "url": url,
                        "file_name": file_name,
                        "size": size,
                        "file_type": file_type,
                        "path": dir_path,
                    }

        if is_html_dir_like:
            folder_path = f"{dir_path.rstrip('/')}/{file_name}".replace("//", "/")
            self.create_folder_structure(folder_path, url)
            self._debug(f"add_folder_like path={folder_path} from_url={url}")
            return

        ext = normalize_extension(file_name)
        if not self.filter_file_type(file_name):
            return
        icon, group = self._file_icon_and_group(file_name, file_type)
        display_type = group if not file_type else f"{group} | {file_type}"

        node_id = self.tree.insert(
            parent_id,
            "end",
            text=f"{icon} {file_name}",
            values=(size or "", display_type, full_path or ""),
            tags=("file", ext),
        )
        if full_path:
            self.tree.set(node_id, "#0", f"{icon} {file_name}")
        if full_path and full_path in self.checked_items:
            self._set_item_checked_visual(node_id, True)
            tags = list(self.tree.item(node_id, "tags"))
            if "checked" not in tags:
                tags.append("checked")
                self.tree.item(node_id, tags=tuple(tags))
        self._debug(
            f"add_file name={file_name} full_path={full_path} parent={parent_id or '/'} from_cache={from_cache}"
        )

    def filter_file_type(self, file_name: str) -> bool:
        ext = normalize_extension(file_name)
        var = self.file_types.get(ext)
        if var is None:
            return True
        return bool(var.get())

    def update_file_types(self, file_name: str) -> None:
        ext = normalize_extension(file_name)
        self.file_type_counts[ext] = self.file_type_counts.get(ext, 0) + 1
        if ext not in self.file_types:
            self.file_types[ext] = tk.BooleanVar(value=True)
            self.redraw_file_type_filters()
            return
        widget = self.file_type_widgets.get(ext)
        if widget is not None:
            widget.configure(text=f"{ext} ({self.file_type_counts.get(ext, 0)})")

    def redraw_file_type_filters(self):
        for widget in self.filters_container.winfo_children():
            widget.destroy()
        self.file_type_widgets.clear()
        for ext in sorted(self.file_types.keys()):
            cb = tk.Checkbutton(
                self.filters_container,
                text=f"{ext} ({self.file_type_counts.get(ext, 0)})",
                variable=self.file_types[ext],
                command=self.apply_filters,
                anchor="w",
                relief="flat",
                highlightthickness=0,
                padx=6,
                pady=2,
            )
            cb.pack(side=LEFT, padx=6)
            self.file_type_widgets[ext] = cb

    def apply_filters(self) -> None:
        before = len(self._all_tree_items())
        for item in self.tree.get_children(""):
            self.tree.delete(item)
        with self.folders_dict_lock:
            self.folders.clear()

        with self.files_dict_lock:
            items = list(self.files_dict.items())
        for full_path, info in items:
            file_name = info.get("file_name")
            if not file_name:
                continue
            if not self.filter_file_type(file_name):
                continue
            self._add_file_to_tree(
                info.get("path") or "",
                info.get("url") or "",
                file_name,
                info.get("size"),
                info.get("file_type"),
                full_path,
                from_cache=True,
            )
        after = len(self._all_tree_items())
        self._debug(
            f"apply_filters files_dict={len(items)} visible_before={before} visible_after={after}"
        )

    def clear_scan_results(self) -> None:
        if self.is_scanning:
            return
        for item in self.tree.get_children(""):
            self.tree.delete(item)
        with self.files_dict_lock:
            self.files_dict.clear()
        with self.folders_dict_lock:
            self.folders.clear()
        for widget in self.filters_container.winfo_children():
            widget.destroy()
        self.file_types.clear()
        self.file_type_counts.clear()
        self.file_type_widgets.clear()
        self.checked_items.clear()
        self.progress_var.set(0)
        self.progress_label.configure(text="")
        self._set_status("Ready", "success")

    def start_scan(self) -> None:
        url = self.url_var.get().strip()
        if self.is_scanning:
            self.backend.should_stop = True
            self.backend.should_stop = True
            self._set_status("Stopping", "warning")
            return
        if not url:
            self.notify_error("Error", "Please enter a URL")
            return

        self.backend.should_stop = False
        self.backend.should_stop = False
        self.search_var.set("")
        self.full_tree_backup.clear()
        try:
            self.download_path = default_download_folder(url, os.getcwd())
        except Exception:
            self.download_path = os.path.join(os.getcwd(), "downloads")

        t = threading.Thread(target=self.backend.scan_website, args=(url,), daemon=True)
        t.start()

    def _ensure_download_item(self, file_path: str, display_name: str):
        item = self.download_items.get(file_path)
        if item:
            return item["cancel_event"]

        row = ttkb.Frame(self.downloads_container)
        row.pack(fill=X, pady=3)
        name = ttkb.Label(row, text=display_name)
        name.pack(side=LEFT, padx=(0, 8))
        bar_var = tk.DoubleVar(value=0)
        bar = ttkb.Progressbar(row, variable=bar_var, maximum=100, bootstyle="info")
        bar.pack(side=LEFT, fill=X, expand=True)
        status = ttkb.Label(row, text="Queued")
        status.pack(side=LEFT, padx=8)
        cancel_event = threading.Event()

        def do_cancel():
            cancel_event.set()
            try:
                status.configure(text="Canceling...")
            except tk.TclError:
                pass

        cancel_btn = ttkb.Button(row, text="Cancel", bootstyle="danger", width=8, command=do_cancel)
        cancel_btn.pack(side=RIGHT, padx=(8, 0))

        self.download_items[file_path] = {
            "frame": row,
            "bar_var": bar_var,
            "status": status,
            "cancel_event": cancel_event,
        }
        return cancel_event

    def update_progress(self, file_path, file_name, progress):
        self._run_on_ui_thread(self._update_progress_ui, file_path, file_name, progress)

    def _update_progress_ui(self, file_path, file_name, progress):
        item = self.download_items.get(file_path)
        if item:
            try:
                item["bar_var"].set(progress)
                item["status"].configure(text=f"Downloading {progress:.1f}%")
            except tk.TclError:
                pass
            return

        self.progress_var.set(progress)
        self.progress_label.configure(text=f"Downloading: {file_name} ({progress:.1f}%)")

    def update_download_status(self, file_path, status_text):
        self._run_on_ui_thread(self._update_download_status_ui, file_path, status_text)

    def _update_download_status_ui(self, file_path, status_text):
        item = self.download_items.get(file_path)
        if not item:
            return
        try:
            item["status"].configure(text=status_text)
        except tk.TclError:
            pass

    def on_downloads_finished(self, completed, total):
        self._run_on_ui_thread(self.downloads_completed, completed, total)

    def downloads_completed(self, completed, total):
        self.pause_btn.configure(state="disabled")
        self.progress_var.set(0)
        self.progress_label.configure(text=f"Downloads: {completed}/{total}")
        self._set_status("Ready", "success")

    def download_selected(self) -> None:
        if not self.download_path:
            url = self.url_var.get().strip()
            if url:
                try:
                    self.download_path = default_download_folder(url, os.getcwd())
                except Exception:
                    self.download_path = os.path.join(os.getcwd(), "downloads")
            else:
                self.download_path = os.path.join(os.getcwd(), "downloads")

        os.makedirs(self.download_path, exist_ok=True)

        selected = []
        with self.files_dict_lock:
            for full_path in sorted(self.checked_items):
                info = self.files_dict.get(full_path)
                if info:
                    selected.append((full_path, info))
            if not selected:
                selected_item_ids = list(self.tree.selection())
                for item_id in selected_item_ids:
                    try:
                        tags = self.tree.item(item_id, "tags")
                    except tk.TclError:
                        continue
                    if "file" not in tags:
                        continue
                    full_path = self.tree.set(item_id, "full_path")
                    if not full_path:
                        continue
                    info = self.files_dict.get(full_path)
                    if info:
                        selected.append((full_path, info))

        if not selected:
            self.notify_info("Info", "No selected files to download")
            return

        self.pause_btn.configure(state="normal")
        futures = []
        for full_path, info in selected:
            url = info.get("url")
            file_name = info.get("file_name")
            if not url or not file_name:
                continue

            safe_name = sanitize_filename(file_name)
            file_path = safe_join(self.download_path, [safe_name])

            cancel_event = self._ensure_download_item(file_path, safe_name)
            futures.append(self.executor.submit(self.backend.download_file, url, file_path, safe_name, cancel_event))

        monitor = threading.Thread(target=self.backend.monitor_downloads, args=(futures,), daemon=True)
        monitor.start()

    def apply_search_filter(self) -> None:
        term = (self.search_var.get() or "").strip().lower()
        if not term:
            if self.full_tree_backup:
                self._restore_full_tree()
            return

        if not self.full_tree_backup:
            self._backup_full_tree()
        self._filter_tree_by_term(term)

    def on_search_filter_changed(self, *_):
        self.apply_search_filter()

    def _backup_full_tree(self) -> None:
        self.full_tree_backup.clear()
        for item in self._all_tree_items():
            self.full_tree_backup[item] = {
                "parent": self.tree.parent(item),
                "index": self.tree.index(item),
                "text": self.tree.item(item, "text"),
                "values": self.tree.item(item, "values"),
                "tags": self.tree.item(item, "tags"),
                "open": self.tree.item(item, "open"),
            }

    def _restore_full_tree(self) -> None:
        backup = dict(self.full_tree_backup)
        self.full_tree_backup.clear()
        for item in self.tree.get_children(""):
            self.tree.delete(item)
        with self.folders_dict_lock:
            self.folders.clear()

        items_sorted = sorted(backup.items(), key=lambda kv: (kv[1]["parent"], kv[1]["index"]))
        id_map = {}
        for old_id, data in items_sorted:
            parent_old = data["parent"]
            parent_new = id_map.get(parent_old, "") if parent_old else ""
            new_id = self.tree.insert(parent_new, "end", text=data["text"], values=data["values"], tags=data["tags"])
            self.tree.item(new_id, open=data["open"])
            id_map[old_id] = new_id

    def _filter_tree_by_term(self, term: str) -> None:
        for item in self._all_tree_items():
            text = (self.tree.item(item, "text") or "").lower()
            if term in text:
                continue
            try:
                self.tree.detach(item)
            except tk.TclError:
                pass

    def _all_tree_items(self):
        out = []
        stack = list(self.tree.get_children(""))
        while stack:
            item = stack.pop()
            out.append(item)
            stack.extend(self.tree.get_children(item))
        return out

    def get_all_tree_items(self, parent=""):
        if parent == "":
            return self._all_tree_items()
        out = []
        for child in self.tree.get_children(parent):
            out.append(child)
            out.extend(self.get_all_tree_items(child))
        return out

    def _get_ancestors(self, item):
        ancestors = []
        try:
            parent = self.tree.parent(item)
            while parent:
                ancestors.append(parent)
                parent = self.tree.parent(parent)
        except tk.TclError:
            return []
        return ancestors

    def _strip_checkmark(self, text: str) -> str:
        if text.startswith(self.checkbox_checked):
            return text[len(self.checkbox_checked) :]
        return text

    def _file_icon_and_group(self, file_name: str, file_type: str | None):
        ext = normalize_extension(file_name)
        mime = (file_type or "").lower()
        if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico"):
            return "🖼", "image"
        if ext in (".md", ".txt", ".pdf", ".doc", ".docx", ".rtf"):
            return "📄", "document"
        if ext in (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"):
            return "🗜", "archive"
        if ext in (
            ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".cpp",
            ".h", ".hpp", ".json", ".yaml", ".yml", ".toml", ".xml", ".html", ".css", ".sh",
        ):
            return "💻", "code"
        if "text/" in mime:
            return "📄", "text"
        if "image/" in mime:
            return "🖼", "image"
        if "audio/" in mime:
            return "🎵", "audio"
        if "video/" in mime:
            return "🎬", "video"
        return "📦", "binary"

    def _set_item_checked_visual(self, item: str, checked: bool) -> None:
        try:
            text = self.tree.item(item, "text")
        except tk.TclError:
            return
        raw = self._strip_checkmark(text or "")
        display = f"{self.checkbox_checked}{raw}" if checked else raw
        try:
            self.tree.item(item, text=display)
        except tk.TclError:
            return

    def _focused_tree_item(self):
        try:
            item = self.tree.focus()
            if item and self.tree.exists(item):
                return item
            selected = self.tree.selection()
            if selected:
                return selected[0]
        except tk.TclError:
            return ""
        return ""

    def toggle_check(self, item, force_check=None):
        try:
            if not self.tree.exists(item):
                return
            tags = list(self.tree.item(item, "tags"))
        except tk.TclError:
            return

        is_checked = "checked" in tags
        new_checked = (not is_checked) if force_check is None else bool(force_check)

        if "file" in tags:
            full_path = self.tree.set(item, "full_path")
            if full_path:
                if new_checked:
                    self.checked_items.add(full_path)
                else:
                    self.checked_items.discard(full_path)

        if new_checked and "checked" not in tags:
            tags.append("checked")
        if (not new_checked) and "checked" in tags:
            tags.remove("checked")
        self.tree.item(item, tags=tuple(tags))
        self._set_item_checked_visual(item, new_checked)

        if "folder" in tags:
            for child in self.tree.get_children(item):
                self.toggle_check(child, force_check=new_checked)

    def on_tree_click(self, event):
        try:
            item = self.tree.identify("item", event.x, event.y)
            if not item:
                return
            self.drag_anchor_item = item
            # Let Treeview default bindings handle selection semantics (shift/cmd drag).
            self.tree.focus(item)
            element = self.tree.identify_element(event.x, event.y)
            if "indicator" in element:
                return
            # Do not toggle check state when modifier-assisted multi-selection is active.
            modifier_mask = 0x0001 | 0x0004 | 0x0008 | 0x0010 | 0x0080
            if event.state & modifier_mask:
                return
            if self.tree.identify_column(event.x) == "#0":
                self.toggle_check(item)
        except tk.TclError:
            return

    def on_tree_drag_select(self, event):
        try:
            if not self.drag_anchor_item:
                return
            target = self.tree.identify_row(event.y)
            if not target:
                return
            items = self._all_tree_items()
            if self.drag_anchor_item not in items or target not in items:
                return
            a = items.index(self.drag_anchor_item)
            b = items.index(target)
            lo, hi = (a, b) if a <= b else (b, a)
            self.tree.selection_set(items[lo : hi + 1])
        except tk.TclError:
            return

    def on_tree_space(self, _event=None):
        item = self._focused_tree_item()
        if item:
            self.toggle_check(item)
            return "break"
        return None

    def on_tree_enter(self, _event=None):
        item = self._focused_tree_item()
        if not item:
            return None
        try:
            tags = self.tree.item(item, "tags")
            if "folder" in tags:
                self.tree.item(item, open=not bool(self.tree.item(item, "open")))
            else:
                self.toggle_check(item)
        except tk.TclError:
            return None
        return "break"

    def show_context_menu(self, event):
        try:
            item = self.tree.identify_row(event.y)
            if item:
                self.tree.focus(item)
                self.tree.selection_set(item)
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()
        return "break"

    def select_all(self):
        for item in self._all_tree_items():
            self.toggle_check(item, force_check=True)

    def deselect_all(self):
        for item in self._all_tree_items():
            self.toggle_check(item, force_check=False)

    def expand_all(self, parent=""):
        for item in self.tree.get_children(parent):
            self.tree.item(item, open=True)
            self.expand_all(item)

    def collapse_all(self, parent=""):
        for item in self.tree.get_children(parent):
            self.tree.item(item, open=False)
            self.collapse_all(item)

    def select_all_types(self):
        for var in self.file_types.values():
            var.set(True)
        self.apply_filters()

    def deselect_all_types(self):
        for var in self.file_types.values():
            var.set(False)
        self.apply_filters()

    def toggle_panels(self):
        if self.panels_visible:
            self.panels_notebook.grid_remove()
            self.panels_visible = False
            self.toggle_panels_btn.configure(text="Show Panels")
        else:
            self.panels_notebook.grid()
            self.panels_visible = True
            self.toggle_panels_btn.configure(text="Hide Panels")

    def _on_tree_select_all(self, _event=None):
        self.select_all()
        return "break"

    def on_tree_select_all(self, _event=None):
        return self._on_tree_select_all(_event)

    def _safe_create_folder_and_add_file(
        self, dir_path, url, file_name, size, file_type, full_path
    ):
        self._add_file_to_tree(dir_path, url, file_name, size, file_type, full_path)

    def focus_search(self, _event=None):
        try:
            self.search_entry.focus_set()
        except tk.TclError:
            pass

    def focus_logs(self, _event=None):
        try:
            if self.panels_notebook is not None and self.logs_tab is not None:
                self.panels_notebook.select(self.logs_tab)
            self.log_text.focus_set()
        except (AttributeError, tk.TclError):
            pass

    def clear_search(self, _event=None):
        self.search_var.set("")

    def sort_tree(self, col):
        try:
            items = [(self.tree.set(i, col), i) for i in self.tree.get_children("")]
            items.sort(reverse=self.sort_reverse)
            for index, (_, i) in enumerate(items):
                self.tree.move(i, "", index)
            self.sort_reverse = not self.sort_reverse
        except tk.TclError:
            pass

    def on_closing(self):
        try:
            self.backend.should_stop = True
            self.executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def run(self) -> None:
        if self._ui_smoke:
            try:
                for _ in range(3):
                    self.window.update_idletasks()
                    self.window.update()
            finally:
                try:
                    self.window.destroy()
                except tk.TclError:
                    pass
            return
        self.window.mainloop()
