from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
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

@dataclass
class TreeNode:
    node_id: str
    parent_id: str        # "" for root-level nodes
    name: str
    kind: str             # "folder" | "file"
    full_path: str        # "" for folders
    size: str
    file_type: str
    icon_group: str       # "folder"|"image"|"document"|"archive"|"code"|"audio"|"video"|"text"|"binary"
    checked: bool = False
    expanded: bool = False
    hidden: bool = False  # True when filtered out by search
    children: list[str] = field(default_factory=list)  # ordered list of child node_ids


_EMOJI_ICONS = {
    "folder":   "📁",
    "image":    "🖼️",
    "document": "📄",
    "archive":  "🗜️",
    "code":     "💻",
    "audio":    "🎵",
    "video":    "🎬",
    "text":     "📝",
    "binary":   "⚙️",
}

_BG_NORMAL        = ("gray95", "gray17")
_BG_HOVER         = ("#E2E8F0", "#2D3748")
_BG_CHECKED       = ("#DBEAFE", "#1E3A5F")
_BG_CHECKED_HOVER = ("#BFDBFE", "#1E40AF")


class RowWidget:
    """One visible row in the FileTree."""

    INDENT_PX = 20
    ROW_HEIGHT = 34

    def __init__(self, parent, app, node: TreeNode, depth: int):
        self.app = app
        self.node_id = node.node_id
        self._checked = node.checked
        self._hovered = False

        self.frame = ctk.CTkFrame(parent, height=self.ROW_HEIGHT, corner_radius=4)
        self.frame.pack(fill="x", padx=4, pady=1)
        self.frame.pack_propagate(False)

        # Indent spacer
        if depth > 0:
            ctk.CTkFrame(
                self.frame, width=depth * self.INDENT_PX,
                fg_color="transparent", height=self.ROW_HEIGHT,
            ).pack(side="left")

        # Chevron (folders) or invisible spacer (files)
        if node.kind == "folder":
            self.chevron = ctk.CTkButton(
                self.frame, text="▶" if not node.expanded else "▼",
                width=22, height=22, fg_color="transparent",
                hover_color=("gray85", "gray30"), text_color=("gray40", "gray60"),
                font=ctk.CTkFont(size=10),
                command=lambda: app._on_chevron_click(self.node_id),
            )
            self.chevron.pack(side="left", padx=(2, 0))
        else:
            ctk.CTkFrame(
                self.frame, width=26, fg_color="transparent", height=self.ROW_HEIGHT,
            ).pack(side="left")

        # Emoji icon
        ctk.CTkLabel(
            self.frame,
            text=_EMOJI_ICONS.get(node.icon_group, "📄"),
            font=ctk.CTkFont(size=16),
            width=28,
        ).pack(side="left", padx=(2, 4))

        # Name label
        self.name_label = ctk.CTkLabel(
            self.frame,
            text=node.name,
            anchor="w",
            font=ctk.CTkFont(size=13, weight="bold" if node.kind == "folder" else "normal"),
        )
        self.name_label.pack(side="left", fill="x", expand=True)

        # Size + type (right side, files only)
        if node.kind == "file":
            if node.size:
                ctk.CTkLabel(
                    self.frame,
                    text=node.size,
                    font=ctk.CTkFont(size=11),
                    text_color=("gray50", "gray60"),
                    width=80,
                    anchor="e",
                ).pack(side="right", padx=(0, 4))
            if node.icon_group and node.icon_group != "binary":
                ctk.CTkLabel(
                    self.frame,
                    text=node.icon_group,
                    font=ctk.CTkFont(size=10),
                    text_color=("gray50", "gray60"),
                    width=60,
                    anchor="e",
                ).pack(side="right", padx=(0, 2))

        self._update_bg()

        # Bind hover + click on frame and all children
        self._bind_all(self.frame)

    def _bind_all(self, widget) -> None:
        # Skip chevron button — it has its own command; don't overlay _on_click
        if hasattr(self, "chevron") and widget is self.chevron:
            return
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)
        widget.bind("<Button-1>", self._on_click)
        for child in widget.winfo_children():
            self._bind_all(child)

    def _on_enter(self, _event=None) -> None:
        self._hovered = True
        self._update_bg()

    def _on_leave(self, _event=None) -> None:
        self._hovered = False
        self._update_bg()

    def _on_click(self, event) -> None:
        self.app._on_row_click(self.node_id, event)

    def set_checked(self, checked: bool) -> None:
        self._checked = checked
        self._update_bg()

    def set_chevron(self, expanded: bool) -> None:
        if hasattr(self, "chevron"):
            self.chevron.configure(text="▼" if expanded else "▶")

    def _update_bg(self) -> None:
        if self._checked and self._hovered:
            color = _BG_CHECKED_HOVER
        elif self._checked:
            color = _BG_CHECKED
        elif self._hovered:
            color = _BG_HOVER
        else:
            color = _BG_NORMAL
        self.frame.configure(fg_color=color)

    def destroy(self) -> None:
        self.frame.destroy()


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

        # FileTree data model
        self.tree_nodes: dict[str, TreeNode] = {}
        self.tree_roots: list[str] = []           # top-level node_ids in insertion order
        self._node_counter: int = 0              # monotonic counter for unique node_ids

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

        if not self._ui_smoke:
            self.window.after(100, self._poll_scan_queue)
            self.window.after(100, self._poll_file_queue)

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
        self._visible_nodes = []
        self._row_widgets = {}
        self.tree_scroll_frame = None
        self.full_tree_backup = {}
        self.sort_reverse = False
        self.drag_anchor_item = ""
        self._last_toggle_time = 0.0
        self._search_after_id = None
        self.tree_nodes = {}
        self.tree_roots = []
        self._node_counter = 0
        self.context_menu = tk.Menu(self.window, tearoff=0)

    def _build_full_ui(self) -> None:
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_filters_row()
        self._build_filetree()
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

    # --- Queue polling (thread-safe) ---

    def _schedule_flush(self) -> None:
        """Schedule a deferred flush of scan_item_buffer if not already pending."""
        if self.scan_flush_job is not None:
            return
        if not self.is_scanning and self.scan_item_buffer.empty():
            return
        self.scan_flush_job = self.window.after(
            self.scan_flush_interval_ms, self._flush_scan_buffer
        )

    def _flush_scan_buffer(self, max_items: int | None = None, reschedule: bool = True) -> None:
        """Drain scan_item_buffer in batches and dispatch to dir/file queues."""
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
                self.dir_queue.put((path, url))
                added_dir = True
            else:
                self.file_queue.put((path, url, file_name, size, file_type, full_path))
                added_file = True
            processed += 1

        if added_dir and not self.is_processing_dirs:
            self.window.after(0, self._poll_scan_queue)
        if added_file and not self.is_processing_files:
            self.window.after(0, self._poll_file_queue)

        if reschedule and not self.scan_item_buffer.empty():
            self._schedule_flush()

    def _poll_scan_queue(self) -> None:
        """Process one item from dir_queue and reschedule until empty."""
        try:
            self.is_processing_dirs = True
            if not self.dir_queue.empty():
                dir_path, url = self.dir_queue.get()
                self.add_folder(dir_path, url)
                self.window.after(10, self._poll_scan_queue)
            else:
                self.is_processing_dirs = False
        except tk.TclError:
            self.is_processing_dirs = False

    def _poll_file_queue(self) -> None:
        """Process one item from file_queue and reschedule until empty."""
        try:
            self.is_processing_files = True
            qsize = self.file_queue.qsize()
            if qsize != self._last_logged_queue_size and (qsize <= 5 or qsize % 100 == 0):
                self._debug(f"_poll_file_queue queue_size={qsize}")
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
                self.add_file(dir_path, url, file_name, size, file_type, full_path)
                self.window.after(5, self._poll_file_queue)
            else:
                self.is_processing_files = False
        except tk.TclError:
            self.is_processing_files = False

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

    def _build_filetree(self) -> None:
        outer = ctk.CTkFrame(self.window, fg_color="transparent")
        outer.grid(row=2, column=0, sticky="nsew", padx=10, pady=(4, 0))
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(1, weight=1)

        # Search bar
        search_bar = ctk.CTkFrame(outer, fg_color="transparent")
        search_bar.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        search_bar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(search_bar, text="Search").grid(row=0, column=0, padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(search_bar, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, sticky="ew")
        self.search_var.trace_add("write", self.on_search_filter_changed)

        # Scrollable tree container
        self.tree_scroll_frame = ctk.CTkScrollableFrame(
            outer,
            fg_color=("gray95", "gray17"),
            corner_radius=8,
        )
        self.tree_scroll_frame.grid(row=1, column=0, sticky="nsew")

        # Runtime state for view layer
        self._visible_nodes: list[str] = []
        self._row_widgets: dict[str, RowWidget] = {}

    def _build_progress_section(self) -> None:
        progress_frame = ctk.CTkFrame(self.window, fg_color="transparent")
        progress_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(4, 0))
        progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=0, sticky="ew")

        self.progress_label = ctk.CTkLabel(progress_frame, text="")
        self.progress_label.grid(row=1, column=0, sticky="w")

    def _build_panels(self) -> None:
        self.panels_notebook = ctk.CTkTabview(self.window, height=180)
        self.panels_notebook.grid(row=4, column=0, sticky="ew", padx=10, pady=(4, 10))
        self._panels_widget = self.panels_notebook  # toggle_panels 用

        downloads_tab = self.panels_notebook.add("Downloads")
        logs_tab = self.panels_notebook.add("Logs")
        self.panels_notebook.set("Logs")  # 預設顯示 Logs

        # Downloads tab：可捲動容器 + DownloadsPanel
        downloads_scroll = ctk.CTkScrollableFrame(downloads_tab, height=120)
        downloads_scroll.pack(fill="both", expand=True)
        self.downloads_panel = DownloadsPanel(
            parent_frame=downloads_scroll,
            ctk=ctk,
            tk=tk,
            tokens=self.ui_tokens,
        )

        # Logs tab：CTkTextbox
        self.log_text = ctk.CTkTextbox(logs_tab, height=120, wrap="word")
        self.log_text.pack(fill="both", expand=True)

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
        try:
            self.search_entry.focus_set()
        except tk.TclError:
            pass

    def focus_logs(self, event=None) -> None:
        try:
            if hasattr(self, "panels_notebook") and self.panels_notebook is not None:
                self.panels_notebook.set("Logs")
            self.log_text.focus_set()
        except (AttributeError, tk.TclError):
            pass

    def clear_search(self, event=None) -> None:
        if hasattr(self, "search_var"):
            self.search_var.set("")

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

    # --- Status color mapping ---

    _STATUS_COLORS = {
        "success": "#059669",
        "danger": "#DC2626",
        "warning": "#B45309",
        "secondary": "#64748B",
        "info": "#0284C7",
    }

    # --- Backend bridge: scan ---

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

    def start_scan(self) -> None:
        url = self.url_var.get().strip()
        if self.is_scanning:
            self.backend.should_stop = True
            self._set_status("Stopping", "#B45309")
            return
        if not url:
            self.notify_error("Error", "Please enter a URL")
            return

        self.backend.should_stop = False
        self.search_var.set("")
        self.full_tree_backup.clear()
        try:
            self.download_path = default_download_folder(url, os.getcwd())
        except Exception:
            self.download_path = os.path.join(os.getcwd(), "downloads")

        t = threading.Thread(target=self.backend.scan_website, args=(url,), daemon=True)
        t.start()

    def toggle_scan_pause(self) -> None:
        if self.scan_pause_event.is_set():
            self.scan_pause_event.clear()
            self.scan_pause_btn.configure(text="Resume Scan", state="normal")
            self._set_status("Scan Paused", "#B45309")
        else:
            self.scan_pause_event.set()
            self.scan_pause_btn.configure(text="Pause Scan", state="normal")
            self._set_status("Scanning", "#0284C7")

    def clear_scan_results(self) -> None:
        if self.is_scanning:
            return
        for item in self.tree.get_children(""):
            self.tree.delete(item)
        with self.files_dict_lock:
            self.files_dict.clear()
        with self.folders_dict_lock:
            self.folders.clear()
        if hasattr(self, "filters_container"):
            for widget in self.filters_container.winfo_children():
                widget.destroy()
        self.file_types.clear()
        self.file_type_counts.clear()
        self.file_type_widgets.clear()
        self.checked_items.clear()
        self.progress_bar.set(0)
        self.progress_label.configure(text="")
        self._set_status("Ready", "#059669")

    def update_progress(self, scanned: int, total: int) -> None:
        """Update the scan progress bar (0–100%)."""
        if total <= 0:
            self.progress_bar.set(0)
            return
        pct = (scanned / total) * 100
        self.progress_bar.set(pct / 100)
        self.progress_label.configure(text=f"Scan: {scanned}/{total}")

    def add_folder(self, dir_path: str, url: str) -> str:
        """Create folder nodes in the treeview for the given path."""
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

    def add_file(self, dir_path: str, url: str, file_name: str, size, file_type: str, full_path: str) -> None:
        """Add a file row to the treeview."""
        if not file_name:
            return
        is_html_dir_like = (
            isinstance(file_type, str)
            and "text/html" in file_type.lower()
            and "." not in (file_name or "")
        )
        parent_id = self.add_folder(dir_path, url)
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
            self.add_folder(folder_path, url)
            return

        ext = normalize_extension(file_name)
        self._add_file_type_filter(ext)
        var = self.file_types.get(ext)
        if var is not None and not var.get():
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
        if full_path and full_path in self.checked_items:
            self._set_item_checked_visual(node_id, True)
            tags = list(self.tree.item(node_id, "tags"))
            if "checked" not in tags:
                tags.append("checked")
                self.tree.item(node_id, tags=tuple(tags))

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

    # --- Backend bridge: downloads ---

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

        # Step 1: Collect candidate full_paths from the treeview without holding
        # files_dict_lock, since treeview operations must happen on the UI thread
        # and should not be interleaved with background lock-holding work.
        checked_paths: list[str] = []
        for item_id in self._all_tree_items():
            try:
                tags = self.tree.item(item_id, "tags")
            except tk.TclError:
                continue
            if "checked" in tags and "file" in tags:
                full_path = self.tree.set(item_id, "full_path")
                if full_path:
                    checked_paths.append(full_path)

        # Fall back to treeview selection when nothing is checked.
        if not checked_paths:
            for item_id in list(self.tree.selection()):
                try:
                    tags = self.tree.item(item_id, "tags")
                except tk.TclError:
                    continue
                if "file" not in tags:
                    continue
                full_path = self.tree.set(item_id, "full_path")
                if full_path:
                    checked_paths.append(full_path)

        if not checked_paths:
            self.notify_info("Info", "No selected files to download")
            return

        # Step 2: Hold lock only for the brief dict look-ups; copy info so the
        # lock is released before any further work.
        selected: list[tuple[str, dict]] = []
        with self.files_dict_lock:
            for full_path in checked_paths:
                info = self.files_dict.get(full_path)
                if info:
                    selected.append((full_path, dict(info)))

        if not selected:
            self.notify_info("Info", "No selected files to download")
            return

        # Step 3: Submit download tasks without holding the lock.
        self.pause_btn.configure(state="normal")
        futures = []
        for full_path, info in selected:
            url = info.get("url")
            file_name = info.get("file_name")
            if not url or not file_name:
                continue

            safe_name = sanitize_filename(file_name)
            file_path = safe_join(self.download_path, [safe_name])

            cancel_event = self.downloads_panel.ensure(file_path, safe_name)
            futures.append(self.executor.submit(self.backend.download_file, url, file_path, safe_name, cancel_event))

        monitor = threading.Thread(target=self.backend.monitor_downloads, args=(futures,), daemon=True)
        monitor.start()

    def toggle_pause(self) -> None:
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_btn.configure(text="Resume")
            self.progress_label.configure(text="Downloads paused")
        else:
            self.pause_event.set()
            self.pause_btn.configure(text="Pause")
            self.progress_label.configure(text="")

    def _update_download_progress(self, file_path: str, progress: float) -> None:
        self.downloads_panel.set_progress(file_path, progress)

    def _set_download_status(self, file_path: str, text: str) -> None:
        self.downloads_panel.set_status(file_path, text)

    # --- Backend bridge: search ---

    def on_search_filter_changed(self, *args):
        query = self.search_var.get() if hasattr(self, "search_var") else ""
        self._apply_search_filter(query)

    def _apply_search_filter(self, query: str) -> None:
        term = (query or "").strip().lower()
        if not term:
            if self.full_tree_backup:
                self._restore_full_tree()
            return
        if not self.full_tree_backup:
            self._backup_full_tree()
        self._filter_tree_by_term(term)

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
        # Snapshot folders so _restore_full_tree can rebuild the mapping.
        with self.folders_dict_lock:
            self._folders_backup = dict(self.folders)

    def _restore_full_tree(self) -> None:
        backup = dict(self.full_tree_backup)
        self.full_tree_backup.clear()
        folders_snapshot = getattr(self, "_folders_backup", {})
        self._folders_backup = {}

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

        # Rebuild self.folders by remapping old item IDs → new item IDs.
        with self.folders_dict_lock:
            for folder_path, old_id in folders_snapshot.items():
                new_id = id_map.get(old_id)
                if new_id:
                    self.folders[folder_path] = new_id

    def _filter_tree_by_term(self, term: str) -> None:
        for item in self._all_tree_items():
            text = (self.tree.item(item, "text") or "").lower()
            if term in text:
                continue
            try:
                self.tree.detach(item)
            except tk.TclError:
                pass

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
