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
    configure_treeview_style,
    treeview_tag_colors,
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
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_filters_row()
        self._build_treeview()
        self._build_progress_section()
        self._build_panels()
        self._build_download_controls()

        self.sort_reverse = False
        self.full_tree_backup = {}
        self.drag_anchor_item = ""

        self.context_menu = tk.Menu(self.window, tearoff=0)
        self.context_menu.add_command(label="Select All", command=self.select_all)
        self.context_menu.add_command(label="Deselect All", command=self.deselect_all)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Expand All", command=self.expand_all)
        self.context_menu.add_command(label="Collapse All", command=self.collapse_all)

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self.window, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="URL", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )

        self.url_var = tk.StringVar()
        self.url_entry = ctk.CTkEntry(header, textvariable=self.url_var, placeholder_text="https://")
        self.url_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))

        self.status_label = ctk.CTkLabel(header, text="Ready", text_color="#059669")
        self.status_label.grid(row=0, column=2, sticky="e", padx=(0, 8))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=3, sticky="e")

        self.scan_btn = ctk.CTkButton(actions, text="Scan", command=self.start_scan)
        self.scan_btn.pack(side="left", padx=3)

        self.scan_pause_btn = ctk.CTkButton(
            actions, text="Pause Scan",
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
            command=self.toggle_scan_pause,
            state="disabled",
        )
        self.scan_pause_btn.pack(side="left", padx=3)

        self.clear_scan_btn = ctk.CTkButton(
            actions, text="Clear",
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
            command=self.clear_scan_results,
        )
        self.clear_scan_btn.pack(side="left", padx=3)

        # URL context menu
        self.url_context_menu = tk.Menu(self.window, tearoff=0)
        self.url_context_menu.add_command(label="Paste", command=self._paste_into_url_entry)

        self.url_entry.bind("<Command-v>", self._on_url_paste)
        self.url_entry.bind("<Command-V>", self._on_url_paste)
        self.url_entry.bind("<Control-v>", self._on_url_paste)
        self.url_entry.bind("<Control-V>", self._on_url_paste)
        self.url_entry.bind("<Shift-Insert>", self._on_url_paste)
        self.url_entry.bind("<Button-2>", self._show_url_context_menu)
        self.url_entry.bind("<Button-3>", self._show_url_context_menu)

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
        self._ctrl_row_frame = ctk.CTkFrame(self.window, fg_color="transparent")
        self._ctrl_row_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(4, 0))
        self._ctrl_row_frame.grid_columnconfigure(0, weight=1)

        filters_frame = ctk.CTkFrame(self._ctrl_row_frame, fg_color="transparent")
        filters_frame.grid(row=0, column=0, sticky="ew")

        self.filters_container = ctk.CTkScrollableFrame(
            filters_frame,
            height=70,
            orientation="horizontal",
            fg_color="transparent",
        )
        self.filters_container.pack(fill="x")

        type_actions = ctk.CTkFrame(filters_frame, fg_color="transparent")
        type_actions.pack(fill="x", pady=(4, 0))

        ctk.CTkButton(
            type_actions,
            text="Select All Types",
            fg_color=("gray80", "gray25"),
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray35"),
            command=self.select_all_types,
            width=140,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            type_actions,
            text="Deselect All Types",
            fg_color=("gray80", "gray25"),
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray35"),
            command=self.deselect_all_types,
            width=150,
        ).pack(side="left")

    def _build_treeview(self) -> None:
        tree_frame = ctk.CTkFrame(self.window, fg_color="transparent")
        tree_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(4, 0))
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(1, weight=1)

        # 搜尋欄
        search_bar = ctk.CTkFrame(tree_frame, fg_color="transparent")
        search_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        search_bar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(search_bar, text="Search").grid(row=0, column=0, padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(search_bar, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, sticky="ew")
        self.search_var.trace_add("write", self.on_search_filter_changed)

        # Treeview
        configure_treeview_style(self.window, ctk, ttk)
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("size", "type", "full_path"),
            show="tree headings",
            selectmode="extended",
        )
        self.tree.heading("#0", text="Path", command=lambda: self.sort_tree("#0"))
        self.tree.heading("size", text="Size", command=lambda: self.sort_tree("size"))
        self.tree.heading("type", text="Type", command=lambda: self.sort_tree("type"))
        self.tree.column("#0", width=600, stretch=True)
        self.tree.column("size", width=120, stretch=False, anchor="e")
        self.tree.column("type", width=240, stretch=False)
        self.tree.column("full_path", width=0, stretch=False)

        tag_colors = treeview_tag_colors(self.window)
        self.tree.tag_configure("checked", foreground=tag_colors["checked"])

        style = ttk.Style()
        style.configure("Treeview", font=("SF Pro Text", 14), rowheight=34)
        style.configure("Treeview.Heading", font=("SF Pro Text", 13, "bold"))

        self.tree.grid(row=1, column=0, sticky="nsew")

        tree_scroll = tk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.grid(row=1, column=1, sticky="ns")

        # 鍵盤與滑鼠綁定
        self.tree.bind("<Command-a>", self._on_tree_select_all)
        self.tree.bind("<Control-a>", self._on_tree_select_all)
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Button-2>", self.show_context_menu)
        self.tree.bind("<Control-Button-1>", self.show_context_menu)
        self.tree.bind("<B1-Motion>", self.on_tree_drag_select)
        self.tree.bind("<space>", self.on_tree_space)
        self.tree.bind("<Return>", self.on_tree_enter)

    def _build_progress_section(self) -> None:
        pass

    def _build_panels(self) -> None:
        pass

    def _build_download_controls(self) -> None:
        controls = ctk.CTkFrame(self._ctrl_row_frame, fg_color="transparent")
        controls.grid(row=0, column=1, sticky="e", padx=(10, 0))

        self.download_btn = ctk.CTkButton(
            controls, text="Download Selected", command=self.download_selected
        )
        self.download_btn.grid(row=0, column=0, padx=4)

        self.pause_btn = ctk.CTkButton(
            controls, text="Pause",
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
            command=self.toggle_pause,
            state="disabled",
        )
        self.pause_btn.grid(row=0, column=1, padx=4)

        self.path_btn = ctk.CTkButton(
            controls, text="Choose Folder",
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
            command=self.choose_download_path,
        )
        self.path_btn.grid(row=0, column=2, padx=4)

        ctk.CTkLabel(controls, text="Threads").grid(row=0, column=3, padx=(12, 4))

        self.threads_var = tk.StringVar(value="5")
        self.threads_combo = ctk.CTkOptionMenu(
            controls,
            values=[str(i) for i in range(1, 11)],
            variable=self.threads_var,
            command=self.update_thread_count,
            width=70,
        )
        self.threads_combo.grid(row=0, column=4)

        self.panels_visible = True
        self.toggle_panels_btn = ctk.CTkButton(
            controls, text="Hide Panels",
            fg_color=("gray80", "gray25"),
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray35"),
            command=self.toggle_panels,
            width=110,
        )
        self.toggle_panels_btn.grid(row=0, column=5, padx=(10, 0))

    def focus_search(self, event=None) -> None:
        pass

    def focus_logs(self, event=None) -> None:
        pass

    def clear_search(self, event=None) -> None:
        pass

    def _on_url_paste(self, _event=None):
        self._paste_into_url_entry()
        return "break"

    def _on_global_url_paste(self, _event=None):
        if not hasattr(self, "url_entry"):
            return None
        try:
            focused = self.window.focus_get()
        except tk.TclError:
            return None
        try:
            if focused is self.url_entry._entry:
                self._paste_into_url_entry()
                return "break"
        except AttributeError:
            pass
        return None

    def _paste_into_url_entry(self):
        try:
            text = self.window.clipboard_get()
        except tk.TclError:
            return
        if not text:
            return
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, text)

    def _show_url_context_menu(self, event):
        try:
            self.url_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.url_context_menu.grab_release()

    def _set_status(self, text: str, color: str = "#059669") -> None:
        try:
            self.status_label.configure(text=text, text_color=color)
        except Exception:
            pass

    # --- Treeview interaction helpers ---

    def _all_tree_items(self):
        out = []
        stack = list(self.tree.get_children(""))
        while stack:
            item = stack.pop()
            out.append(item)
            stack.extend(self.tree.get_children(item))
        return out

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

    def _strip_checkmark(self, text: str) -> str:
        if text.startswith(self.checkbox_checked):
            return text[len(self.checkbox_checked):]
        return text

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
            self.tree.focus(item)
            element = self.tree.identify_element(event.x, event.y)
            if "indicator" in element:
                return
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
            self.tree.selection_set(items[lo: hi + 1])
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

    def _on_tree_select_all(self, _event=None):
        self.select_all()
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

    def sort_tree(self, col: str) -> None:
        def get_key(item_id: str) -> str:
            if col == "#0":
                return self._strip_checkmark(self.tree.item(item_id, "text")).lower()
            return self.tree.set(item_id, col).lower()

        def sort_children(parent: str) -> None:
            children = list(self.tree.get_children(parent))
            if not children:
                return
            children.sort(key=get_key, reverse=self.sort_reverse)
            for idx, item in enumerate(children):
                self.tree.move(item, parent, idx)
            for item in children:
                sort_children(item)

        sort_children("")
        self.sort_reverse = not self.sort_reverse

    def on_search_filter_changed(self, *args):
        pass

    def start_scan(self): pass
    def toggle_scan_pause(self): pass
    def clear_scan_results(self): pass
    def download_selected(self): pass
    def toggle_pause(self): pass

    def choose_download_path(self) -> None:
        path = filedialog.askdirectory(title="Choose Download Location")
        if path:
            self.download_path = path

    def update_thread_count(self, value=None) -> None:
        try:
            n = int(self.threads_var.get())
        except (ValueError, AttributeError):
            return
        self.max_workers = max(1, min(10, n))

    def toggle_panels(self) -> None:
        if self.panels_visible:
            if hasattr(self, "_panels_widget"):
                self._panels_widget.grid_remove()
            self.panels_visible = False
            self.toggle_panels_btn.configure(text="Show Panels")
        else:
            if hasattr(self, "_panels_widget"):
                self._panels_widget.grid()
            self.panels_visible = True
            self.toggle_panels_btn.configure(text="Hide Panels")

    def select_all_types(self) -> None:
        for var in self.file_types.values():
            var.set(True)

    def deselect_all_types(self) -> None:
        for var in self.file_types.values():
            var.set(False)

    def _add_file_type_filter(self, ext: str) -> None:
        if not hasattr(self, "filters_container"):
            return
        if ext in self.file_types:
            return
        var = tk.BooleanVar(value=True)
        self.file_types[ext] = var
        self.file_type_counts[ext] = 0
        cb = ctk.CTkCheckBox(
            self.filters_container,
            text=ext if ext else "(no ext)",
            variable=var,
            onvalue=True,
            offvalue=False,
        )
        cb.pack(side="left", padx=4, pady=4)
        self.file_type_widgets[ext] = cb
