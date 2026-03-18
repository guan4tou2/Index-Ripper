from __future__ import annotations

import copy
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from queue import Empty, Queue

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import customtkinter as ctk

from app_utils import default_download_folder, normalize_extension, safe_join, sanitize_filename, sanitize_path_segment
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

_BG_NORMAL        = "transparent"
_BG_HOVER         = ("#F1F5F9", "#1E293B")
_BG_CHECKED       = ("#EFF6FF", "#172554")
_BG_CHECKED_HOVER = ("#DBEAFE", "#1E3A5F")


class RowWidget:
    """One visible row in the FileTree."""

    INDENT_PX = 20
    ROW_HEIGHT = 36

    def __init__(self, parent, app, node: TreeNode, depth: int):
        self.app = app
        self.node_id = node.node_id
        self._checked = node.checked
        self._hovered = False

        self.frame = ctk.CTkFrame(parent, height=self.ROW_HEIGHT, corner_radius=4)
        self.frame.pack(fill="x", padx=4, pady=0)
        self.frame.pack_propagate(False)

        # 3-px accent bar (left edge, blue when checked)
        self._accent = ctk.CTkFrame(
            self.frame, width=3, corner_radius=0,
            fg_color="#2563EB" if node.checked else "transparent",
        )
        self._accent.pack(side="left", fill="y")

        # Indent spacer
        if depth > 0:
            ctk.CTkFrame(
                self.frame, width=depth * self.INDENT_PX,
                fg_color="transparent", height=self.ROW_HEIGHT,
            ).pack(side="left")

        # Emoji icon
        ctk.CTkLabel(
            self.frame,
            text=_EMOJI_ICONS.get(node.icon_group, "📄"),
            font=ctk.CTkFont(size=18),
            width=28,
        ).pack(side="left", padx=(4, 4))

        # Name label
        self.name_label = ctk.CTkLabel(
            self.frame,
            text=node.name,
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold" if node.kind == "folder" else "normal"),
        )
        self.name_label.pack(side="left", fill="x", expand=True)

        # Chevron on RIGHT (folders only)
        if node.kind == "folder":
            self.chevron = ctk.CTkButton(
                self.frame, text="▼" if node.expanded else "▶",
                width=22, height=22, fg_color="transparent",
                hover_color=("gray85", "gray30"), text_color=("gray40", "gray60"),
                font=ctk.CTkFont(size=10),
                command=lambda: app._on_chevron_click(self.node_id),
            )
            self.chevron.pack(side="right", padx=(4, 4))
        elif node.kind == "file" and node.size:
            # Size label (right side, files only)
            ctk.CTkLabel(
                self.frame,
                text=node.size,
                font=ctk.CTkFont(size=12),
                text_color=("gray50", "gray60"),
                width=80,
                anchor="e",
            ).pack(side="right", padx=(0, 8))

        # Bind hover only on outer frame (avoids <Leave> flicker from child entry)
        self.frame.bind("<Enter>", self._on_enter)
        self.frame.bind("<Leave>", self._on_leave)
        # Bind click on frame and all non-chevron children
        self._bind_clicks(self.frame)

    def _bind_clicks(self, widget) -> None:
        """Bind click handler on widget and all children except the chevron."""
        if hasattr(self, "chevron") and widget is self.chevron:
            return  # chevron has its own command; don't intercept clicks
        widget.bind("<Button-1>", self._on_click)
        for child in widget.winfo_children():
            self._bind_clicks(child)

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
        self._accent.configure(
            fg_color="#2563EB" if checked else "transparent"
        )
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

        # FileTree data model
        self.tree_nodes: dict[str, TreeNode] = {}
        self.tree_roots: list[str] = []           # top-level node_ids in insertion order
        self._node_counter: int = 0              # monotonic counter for unique node_ids
        self._last_toggle_time: float = 0.0      # debounce timestamp for row clicks
        self._tree_update_pending: bool = False  # debounce flag for _schedule_tree_update

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
            # macOS: forward Cmd+V / Cmd+C / Cmd+X / Cmd+A to the focused widget
            # so native clipboard shortcuts work in every CTkEntry / CTkTextbox.
            for seq, virt in (
                ("<Command-v>", "<<Paste>>"),
                ("<Command-V>", "<<Paste>>"),
                ("<Command-c>", "<<Copy>>"),
                ("<Command-C>", "<<Copy>>"),
                ("<Command-x>", "<<Cut>>"),
                ("<Command-X>", "<<Cut>>"),
                ("<Command-z>", "<<Undo>>"),
                ("<Command-Z>", "<<Redo>>"),
            ):
                virt_local = virt  # capture for lambda

                def _fwd(e, _v=virt_local):
                    w = e.widget
                    try:
                        w.event_generate(_v)
                    except Exception:
                        pass
                    return "break"

                self.window.bind(seq, _fwd, add="+")

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
        self._last_toggle_time = 0.0
        self._search_after_id = None
        self.tree_nodes = {}
        self.tree_roots = []
        self._node_counter = 0
        self.scan_pause_btn = type("_Stub", (), {
            "configure": lambda s, **kw: None,
            "grid": lambda s: None,
            "grid_remove": lambda s: None,
        })()
        self._status_dot = type("_Stub", (), {"configure": lambda s, **kw: None})()
        self.context_menu = tk.Menu(self.window, tearoff=0)

    def _build_full_ui(self) -> None:
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_rowconfigure(3, weight=1)   # filetree expands (row shifted by types row)
        self.window.grid_rowconfigure(5, weight=0)   # panels fixed

        self._build_toolbar()
        self._build_filters_row()
        self._build_filetree()
        self._build_progress_section()
        self._build_panels()
        self._build_download_controls()

        self.sort_reverse = False
        self.full_tree_backup = {}

        self.context_menu = tk.Menu(self.window, tearoff=0)
        self.context_menu.add_command(label="Select All", command=self.select_all)
        self.context_menu.add_command(label="Deselect All", command=self.deselect_all)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Expand All", command=self.expand_all)
        self.context_menu.add_command(label="Collapse All", command=self.collapse_all)

    def _build_toolbar(self) -> None:
        toolbar = ctk.CTkFrame(self.window, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        toolbar.grid_columnconfigure(0, weight=1)  # URL entry expands
        toolbar.grid_columnconfigure(2, minsize=96)  # reserve space for pause btn

        self.url_var = tk.StringVar()
        self.url_entry = ctk.CTkEntry(
            toolbar, textvariable=self.url_var,
            placeholder_text="https://",
            font=ctk.CTkFont(size=14),
            height=36,
        )
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        # Scan button (toggles "Scan" ↔ "Stop Scan")
        self.scan_btn = ctk.CTkButton(toolbar, text="Scan", command=self.start_scan, width=90)
        self.scan_btn.grid(row=0, column=1, padx=(0, 4))

        # Pause Scan button — hidden by default, shown only while scanning
        self.scan_pause_btn = ctk.CTkButton(
            toolbar, text="Pause",
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
            command=self.toggle_scan_pause,
            width=80,
            state="disabled",
        )
        self.scan_pause_btn.grid(row=0, column=2, padx=(0, 8))
        self.scan_pause_btn.grid_remove()  # hidden until scan starts

        # Status: dot + text
        status_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        status_frame.grid(row=0, column=3, sticky="e")

        self._status_dot = ctk.CTkFrame(
            status_frame, width=8, height=8, corner_radius=4,
            fg_color="#059669",
        )
        self._status_dot.pack(side="left", padx=(0, 5))
        self._status_dot.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            status_frame, text="Ready",
            text_color="#059669", font=ctk.CTkFont(size=13),
        )
        self.status_label.pack(side="left")

        # URL context menu (right-click paste)
        self.url_context_menu = tk.Menu(self.window, tearoff=0)
        self.url_context_menu.add_command(label="Paste", command=self._paste_into_url_entry)
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

    def on_scan_item(
        self,
        *,
        is_directory: bool,
        path: str,
        url: str,
        file_name: str = "",
        size: str = "",
        file_type: str = "",
        full_path: str = "",
    ) -> None:
        """Backend hook — called from background thread when an item is found."""
        if not self.is_scanning:
            return
        self.scan_item_buffer.put(
            (is_directory, path, url, file_name, size, file_type, full_path)
        )
        self.window.after(0, self._schedule_flush)

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
        # ── Row 1: action buttons ──────────────────────────────────────────
        self._ctrl_row_frame = ctk.CTkFrame(self.window, fg_color="transparent")
        self._ctrl_row_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(6, 0))
        self._ctrl_row_frame.grid_columnconfigure(0, weight=1)

        # ── Row 2: Types label + checkboxes + type-action buttons ──────────
        types_row = ctk.CTkFrame(self.window, fg_color="transparent")
        types_row.grid(row=2, column=0, sticky="ew", padx=10, pady=(4, 0))
        types_row.grid_columnconfigure(2, weight=1)   # checkboxes column expands

        _s = dict(                                    # shared small-button style
            fg_color=("gray80", "gray25"),
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray35"),
            height=28,
            font=ctk.CTkFont(size=12),
        )

        ctk.CTkLabel(
            types_row, text="Types:",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=(0, 6))

        type_btns = ctk.CTkFrame(types_row, fg_color="transparent")
        type_btns.grid(row=0, column=1, sticky="w", padx=(0, 8))
        ctk.CTkButton(type_btns, text="✓ All", command=self.select_all_types,  width=68, **_s).pack(side="left", padx=(0, 4))
        ctk.CTkButton(type_btns, text="✗ All", command=self.deselect_all_types, width=68, **_s).pack(side="left")

        self.filters_container = ctk.CTkScrollableFrame(
            types_row,
            height=38,
            orientation="horizontal",
            fg_color="transparent",
        )
        self.filters_container.grid(row=0, column=2, sticky="ew")
        self._bind_hscroll_wheel(self.filters_container)

    def _build_filetree(self) -> None:
        outer = ctk.CTkFrame(self.window, fg_color="transparent")
        outer.grid(row=3, column=0, sticky="nsew", padx=10, pady=(4, 0))
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
        self.tree_scroll_frame.bind("<Button-2>", self.show_context_menu)
        self.tree_scroll_frame.bind("<Button-3>", self.show_context_menu)
        self.window.bind("<Control-a>", lambda _e: self.select_all())
        self.window.bind("<Command-a>", lambda _e: self.select_all())

        # Runtime state for view layer
        self._visible_nodes: list[str] = []
        self._row_widgets: dict[str, RowWidget] = {}
        self._last_visible: list[str] = []

    def _rebuild_visible(self) -> None:
        """Recompute self._visible_nodes from data model (DFS, respects expanded/hidden)."""
        result: list[str] = []

        def _walk(node_id: str) -> None:
            node = self.tree_nodes.get(node_id)
            if node is None or node.hidden:
                return
            result.append(node_id)
            if node.kind == "folder" and node.expanded:
                for child_id in node.children:
                    _walk(child_id)

        for root_id in self.tree_roots:
            _walk(root_id)

        self._visible_nodes = result

    def _sync_rows(self) -> None:
        """Create/destroy RowWidgets to match _visible_nodes."""
        if self.tree_scroll_frame is None:
            return

        new_ids = set(self._visible_nodes)
        # Remove rows no longer visible
        for node_id in list(self._row_widgets):
            if node_id not in new_ids:
                self._row_widgets.pop(node_id).destroy()

        prev = self._last_visible
        # Append-only optimisation: if the existing rows are still a prefix of
        # the new list (no reordering), just pack the new rows at the end.
        # This prevents the pack_forget→repack flash during scanning.
        if (
            len(self._visible_nodes) >= len(prev)
            and self._visible_nodes[: len(prev)] == prev
            and all(nid in self._row_widgets for nid in prev)
        ):
            for node_id in self._visible_nodes[len(prev) :]:
                node = self.tree_nodes[node_id]
                depth = self._node_depth(node_id)
                self._row_widgets[node_id] = RowWidget(
                    self.tree_scroll_frame, self, node, depth
                )
        else:
            # Full repack needed (expand/collapse, filter, sort, restore)
            for row in list(self._row_widgets.values()):
                row.frame.pack_forget()
            for node_id in self._visible_nodes:
                node = self.tree_nodes[node_id]
                depth = self._node_depth(node_id)
                if node_id not in self._row_widgets:
                    self._row_widgets[node_id] = RowWidget(
                        self.tree_scroll_frame, self, node, depth
                    )
                else:
                    self._row_widgets[node_id].frame.pack(fill="x", padx=4, pady=0)

        self._last_visible = list(self._visible_nodes)

    def _schedule_tree_update(self) -> None:
        """Debounce _rebuild_visible + _sync_rows to avoid O(n²) during bulk add."""
        if not self._tree_update_pending:
            self._tree_update_pending = True
            self.window.after(50, self._do_tree_update)

    def _do_tree_update(self) -> None:
        self._tree_update_pending = False
        self._rebuild_visible()
        self._sync_rows()

    def _node_depth(self, node_id: str) -> int:
        depth = 0
        node = self.tree_nodes.get(node_id)
        while node and node.parent_id:
            depth += 1
            node = self.tree_nodes.get(node.parent_id)
        return depth

    def _next_node_id(self) -> str:
        self._node_counter += 1
        return f"n{self._node_counter}"

    def _on_row_click(self, node_id: str, event=None) -> None:
        now = time.monotonic()
        if now - self._last_toggle_time < 0.25:
            return
        self._last_toggle_time = now
        node = self.tree_nodes.get(node_id)
        if node is None:
            return
        self.toggle_check(node_id)

    def _on_chevron_click(self, node_id: str) -> None:
        node = self.tree_nodes.get(node_id)
        if node is None or node.kind != "folder":
            return
        node.expanded = not node.expanded
        row = self._row_widgets.get(node_id)
        if row:
            row.set_chevron(node.expanded)
        self._rebuild_visible()
        self._sync_rows()

    def _build_progress_section(self) -> None:
        progress_frame = ctk.CTkFrame(self.window, fg_color="transparent")
        progress_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=(6, 2))
        progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(progress_frame, height=14, corner_radius=6)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        self.progress_label = ctk.CTkLabel(
            progress_frame, text="",
            font=ctk.CTkFont(size=13),
            anchor="w",
        )
        self.progress_label.grid(row=1, column=0, sticky="ew")

    def _build_panels(self) -> None:
        self.panels_notebook = ctk.CTkTabview(self.window, height=180)
        self.panels_notebook.grid(row=5, column=0, sticky="ew", padx=10, pady=(4, 10))
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
        _s = dict(
            fg_color=("gray80", "gray25"),
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray35"),
            height=30,
        )

        # Left side of row 1: Select All / Deselect All (file tree)
        sel_frame = ctk.CTkFrame(self._ctrl_row_frame, fg_color="transparent")
        sel_frame.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(sel_frame, text="Select All",   command=self.select_all,   width=100, **_s).pack(side="left", padx=(0, 4))
        ctk.CTkButton(sel_frame, text="Deselect All", command=self.deselect_all, width=110, **_s).pack(side="left")

        # Right side of row 1: download controls
        controls = ctk.CTkFrame(self._ctrl_row_frame, fg_color="transparent")
        controls.grid(row=0, column=1, sticky="e", padx=(10, 0))

        self.download_btn = ctk.CTkButton(
            controls, text="⬇ Download Selected", command=self.download_selected,
            height=30,
        )
        self.download_btn.grid(row=0, column=0, padx=(0, 4))

        self.pause_btn = ctk.CTkButton(
            controls, text="⏸ Pause",
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
            command=self.toggle_pause,
            state="disabled",
            height=30,
        )
        self.pause_btn.grid(row=0, column=1, padx=(0, 4))

        self.path_btn = ctk.CTkButton(
            controls, text="📁 Folder",
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
            command=self.choose_download_path,
            height=30,
        )
        self.path_btn.grid(row=0, column=2, padx=(0, 8))

        ctk.CTkLabel(controls, text="Threads", font=ctk.CTkFont(size=13)).grid(row=0, column=3, padx=(0, 4))

        self.threads_var = tk.StringVar(value="5")
        self.threads_combo = ctk.CTkOptionMenu(
            controls,
            values=[str(i) for i in range(1, 11)],
            variable=self.threads_var,
            command=self.update_thread_count,
            width=70,
            height=30,
        )
        self.threads_combo.grid(row=0, column=4, padx=(0, 8))

        self.panels_visible = True
        self.toggle_panels_btn = ctk.CTkButton(
            controls, text="Hide Panels",
            command=self.toggle_panels,
            width=100,
            **_s,
        )
        self.toggle_panels_btn.grid(row=0, column=5)

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
            self._status_dot.configure(fg_color=color)
        except Exception:
            pass

    # --- Treeview interaction helpers ---

    def _all_tree_items(self) -> list[str]:
        """Return all node_ids in DFS order."""
        out: list[str] = []
        def _walk(node_id: str) -> None:
            out.append(node_id)
            node = self.tree_nodes.get(node_id)
            if node:
                for child_id in node.children:
                    _walk(child_id)
        for root_id in self.tree_roots:
            _walk(root_id)
        return out

    def toggle_check(self, node_id: str, force_check=None, _skip_children: bool = False) -> None:
        node = self.tree_nodes.get(node_id)
        if node is None:
            return
        new_checked = (not node.checked) if force_check is None else bool(force_check)
        node.checked = new_checked

        if node.kind == "file" and node.full_path:
            if new_checked:
                self.checked_items.add(node.full_path)
            else:
                self.checked_items.discard(node.full_path)

        row = self._row_widgets.get(node_id)
        if row:
            row.set_checked(new_checked)

        if node.kind == "folder" and not _skip_children:
            for child_id in node.children:
                self.toggle_check(child_id, force_check=new_checked)

    def show_context_menu(self, event) -> None:
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def select_all(self) -> None:
        for node_id in list(self.tree_nodes):
            self.toggle_check(node_id, force_check=True, _skip_children=True)

    def deselect_all(self) -> None:
        for node_id in list(self.tree_nodes):
            self.toggle_check(node_id, force_check=False, _skip_children=True)

    def expand_all(self, parent: str = "") -> None:
        targets = self.tree_roots if not parent else (
            self.tree_nodes[parent].children if parent in self.tree_nodes else []
        )
        for node_id in targets:
            node = self.tree_nodes.get(node_id)
            if node and node.kind == "folder":
                node.expanded = True
                self.expand_all(node_id)
        if not parent:  # Only rebuild once at top-level call
            self._rebuild_visible()
            self._sync_rows()

    def collapse_all(self, parent: str = "") -> None:
        targets = self.tree_roots if not parent else (
            self.tree_nodes[parent].children if parent in self.tree_nodes else []
        )
        for node_id in targets:
            node = self.tree_nodes.get(node_id)
            if node and node.kind == "folder":
                node.expanded = False
                self.collapse_all(node_id)
        if not parent:  # Only rebuild once at top-level call
            self._rebuild_visible()
            self._sync_rows()

    def sort_tree(self, col: str = "name") -> None:
        def sort_children(children: list[str]) -> None:
            if not children:
                return
            def key(node_id: str) -> str:
                node = self.tree_nodes.get(node_id)
                if node is None:
                    return ""
                if col == "size":
                    return node.size.lower()
                if col == "type":
                    return node.icon_group.lower()
                return node.name.lower()
            children.sort(key=key, reverse=self.sort_reverse)
            for node_id in children:
                node = self.tree_nodes.get(node_id)
                if node:
                    sort_children(node.children)

        sort_children(self.tree_roots)
        self.sort_reverse = not self.sort_reverse
        self._rebuild_visible()
        self._sync_rows()

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

    def _drain_queues(self) -> None:
        """Discard all pending items in scan queues and cancel any scheduled flush."""
        if self.scan_flush_job is not None:
            try:
                self.window.after_cancel(self.scan_flush_job)
            except Exception:
                pass
            self.scan_flush_job = None
        for q in (self.scan_item_buffer, self.dir_queue, self.file_queue):
            while True:
                try:
                    q.get_nowait()
                except Exception:
                    break

    def clear_scan_results(self) -> None:
        if self.is_scanning:
            return
        self._drain_queues()
        self._tree_update_pending = False
        self._last_visible = []

        # Clear data model
        self.tree_nodes.clear()
        self.tree_roots.clear()
        self._node_counter = 0
        with self.folders_dict_lock:
            self.folders.clear()

        # Destroy row widgets
        for row in self._row_widgets.values():
            row.destroy()
        self._row_widgets.clear()
        self._visible_nodes.clear()

        # Clear other state
        with self.files_dict_lock:
            self.files_dict.clear()
        if hasattr(self, "filters_container"):
            for widget in self.filters_container.winfo_children():
                widget.destroy()
        self.file_types.clear()
        self.file_type_counts.clear()
        self.file_type_widgets.clear()
        self.checked_items.clear()
        self.full_tree_backup = {}
        self.scanned_urls = 0
        self.total_urls = 0
        self.progress_bar.set(0)
        self.progress_label.configure(text="")
        self._set_status("Ready", "#059669")

    def on_scan_started(self, *, url: str = "") -> None:
        def _start():
            self.scan_btn.configure(text="Stop Scan")
            self.scan_pause_btn.grid()          # show
            self.scan_pause_btn.configure(state="normal")
            self.progress_bar.set(0)
            self.progress_label.configure(text="Scanning…")
            self._set_status("Scanning", "#B45309")
        self.window.after(0, _start)

    def on_scan_progress(self, *, scanned_urls: int = 0, total_urls: int = 0) -> None:
        self.window.after(0, lambda: self._update_scan_progress(scanned_urls, total_urls))

    def on_scan_finished(self, *, stopped: bool = False) -> None:
        def _finish():
            self.scan_btn.configure(text="Scan")
            self.scan_pause_btn.grid_remove()       # hide
            self.scan_pause_btn.configure(text="Pause", state="disabled")
            if stopped:
                self.progress_bar.set(0)
                self.progress_label.configure(text="Scan stopped")
                self._set_status("Stopped", "#B91C1C")
            else:
                self.progress_bar.set(1)
                n = len(self.files_dict)
                self.progress_label.configure(text=f"Done — {n} files found")
                self._set_status("Ready", "#059669")
        self.window.after(0, _finish)

    def update_progress(self, file_path: str, file_name: str, progress: float) -> None:
        """Backend hook — called from download thread with per-file progress (0–100)."""
        self.window.after(0, lambda: self._update_download_progress(file_path, progress))

    def update_download_status(self, file_path: str, status: str) -> None:
        """Backend hook — called from download thread with file status."""
        self.window.after(0, lambda: self._set_download_status(file_path, status))

    def _update_scan_progress(self, scanned: int, total: int) -> None:
        """Update the scan progress bar (0–100%)."""
        if total <= 0:
            self.progress_bar.set(0)
            return
        pct = scanned / total
        self.progress_bar.set(pct)
        self.progress_label.configure(text=f"Scanning… {scanned}/{total}  ({pct:.0%})")

    def add_folder(self, dir_path: str, url: str) -> str:
        """Ensure all path segments exist as folder nodes; return leaf node_id."""
        if not dir_path:
            dir_path = "/"
        parts = [p for p in dir_path.split("/") if p]

        parent_id = ""
        current_path = ""
        for part in parts:
            current_path = current_path + "/" + part
            with self.folders_dict_lock:
                existing_id = self.folders.get(current_path)
                if not existing_id:
                    node_id = self._next_node_id()
                    node = TreeNode(
                        node_id=node_id,
                        parent_id=parent_id,
                        name=part,
                        kind="folder",
                        full_path="",
                        size="",
                        file_type="",
                        icon_group="folder",
                    )
                    self.tree_nodes[node_id] = node
                    if parent_id:
                        self.tree_nodes[parent_id].children.append(node_id)
                    else:
                        self.tree_roots.append(node_id)
                    self.folders[current_path] = node_id
                    existing_id = node_id
            parent_id = existing_id

        self._schedule_tree_update()
        return parent_id

    def add_file(self, dir_path: str, url: str, file_name: str, size, file_type: str, full_path: str) -> None:
        """Add a file node to the tree."""
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
        self.file_type_counts[ext] = self.file_type_counts.get(ext, 0) + 1
        cb = self.file_type_widgets.get(ext)
        if cb:
            label = ext if ext else "(no ext)"
            cb.configure(text=f"{label} ({self.file_type_counts[ext]})")
        var = self.file_types.get(ext)
        filtered_out = var is not None and not var.get()

        _icon, group = self._file_icon_and_group(file_name, file_type)
        node_id = self._next_node_id()
        node = TreeNode(
            node_id=node_id,
            parent_id=parent_id,
            name=file_name,
            kind="file",
            full_path=full_path or "",
            size=size or "",
            file_type=file_type or "",
            icon_group=group,
            checked=full_path in self.checked_items,
            hidden=filtered_out,
        )
        self.tree_nodes[node_id] = node
        if parent_id:
            self.tree_nodes[parent_id].children.append(node_id)
        else:
            self.tree_roots.append(node_id)

        self._schedule_tree_update()

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
                self.download_path = default_download_folder(url, os.getcwd())
            if not self.download_path:
                self.notify_warning("Warning", "Please choose a download location first.")
                return

        selected_paths = list(self.checked_items)
        if not selected_paths:
            self.notify_info("Info", "No files selected for download.")
            return

        futures = []
        for full_path in selected_paths:
            info = self.files_dict.get(full_path)
            if not info:
                continue
            url = info.get("url")
            file_name = info.get("file_name")
            if not url or not file_name:
                continue

            safe_name = sanitize_filename(file_name)

            # Preserve subfolder structure from the scanned path
            dir_path = info.get("path", "")
            path_segments = [sanitize_path_segment(seg) for seg in dir_path.strip("/").split("/") if seg]
            try:
                target_dir = safe_join(self.download_path, path_segments) if path_segments else self.download_path
                file_path = safe_join(self.download_path, path_segments + [safe_name])
            except ValueError:
                self.log_message(f"[Download] Skipped unsafe path: {full_path}")
                continue
            os.makedirs(target_dir, exist_ok=True)

            cancel_event = self.downloads_panel.ensure(file_path, safe_name)
            futures.append(self.executor.submit(self.backend.download_file, url, file_path, safe_name, cancel_event))

        if not futures:
            return
        try:
            self.pause_btn.configure(state="normal")
        except Exception:
            pass
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
        """Snapshot tree_nodes and tree_roots for search filter restore."""
        self.full_tree_backup = {
            "nodes": copy.deepcopy(self.tree_nodes),
            "roots": list(self.tree_roots),
            "folders": dict(self.folders),
        }

    def _restore_full_tree(self) -> None:
        """Restore tree_nodes from backup (undo search filter)."""
        if not self.full_tree_backup:
            return
        self.tree_nodes = self.full_tree_backup["nodes"]
        self.tree_roots = self.full_tree_backup["roots"]
        with self.folders_dict_lock:
            self.folders = self.full_tree_backup["folders"]
        self.full_tree_backup = {}

        # Destroy all existing row widgets and rebuild from scratch
        for row in self._row_widgets.values():
            row.destroy()
        self._row_widgets.clear()
        self._rebuild_visible()
        self._sync_rows()

    def _filter_tree_by_term(self, term: str) -> None:
        """Mark nodes hidden if they (and their descendants) don't match term."""
        term = term.lower()

        def matches(node_id: str) -> bool:
            node = self.tree_nodes.get(node_id)
            if node is None:
                return False
            if term in node.name.lower() or term in node.full_path.lower():
                return True
            return any(matches(child_id) for child_id in node.children)

        def apply_visibility(node_id: str) -> None:
            node = self.tree_nodes.get(node_id)
            if node is None:
                return
            if matches(node_id):
                node.hidden = False
                if node.kind == "folder":
                    node.expanded = True  # auto-expand matching folders
            else:
                node.hidden = True
            for child_id in node.children:
                apply_visibility(child_id)

        for root_id in self.tree_roots:
            apply_visibility(root_id)

        self._rebuild_visible()
        self._sync_rows()

    def choose_download_path(self) -> None:
        path = filedialog.askdirectory(title="Choose Download Location")
        if path:
            self.download_path = path

    def update_thread_count(self, value=None) -> None:
        try:
            n = int(self.threads_var.get())
        except (ValueError, AttributeError):
            return
        new_count = max(1, min(10, n))
        if new_count == self.max_workers:
            return
        old_executor = self.executor
        self.max_workers = new_count
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        threading.Thread(target=old_executor.shutdown, kwargs={"wait": True, "cancel_futures": False}, daemon=True).start()

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

    def _bind_hscroll_wheel(self, widget) -> None:
        """讓 widget 的滾輪事件橫向捲動 filters_container（平滑版）。"""
        try:
            canvas = self.filters_container._parent_canvas
        except AttributeError:
            return

        # 每個 scroll unit = 20px，讓滾動距離合理
        canvas.configure(xscrollincrement=20)

        def _scroll(event):
            delta = getattr(event, "delta", 0)
            if not delta:
                return
            # macOS trackpad delta 很小 (1–5)；滑鼠滾輪約 120
            # 統一換算為 unit 數，最少 1
            units = max(1, abs(delta) // 3)
            canvas.xview_scroll(-units if delta > 0 else units, "units")

        widget.bind("<MouseWheel>", _scroll, add="+")
        widget.bind("<Shift-MouseWheel>", _scroll, add="+")

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
        self._bind_hscroll_wheel(cb)
        var.trace_add("write", lambda *_: self._on_type_filter_changed(ext))
        self.file_type_widgets[ext] = cb

    def _on_type_filter_changed(self, ext: str) -> None:
        """Show or hide existing tree rows when a file-type checkbox is toggled."""
        if self.full_tree_backup:
            return  # search filter active; handled by _filter_tree_by_term
        var = self.file_types.get(ext)
        if var is None:
            return
        visible = var.get()
        for node in self.tree_nodes.values():
            if node.kind == "file" and normalize_extension(node.name) == ext:
                node.hidden = not visible
        self._rebuild_visible()
        self._sync_rows()


def main():
    app = WebsiteCopierCtk()
    app.run()
