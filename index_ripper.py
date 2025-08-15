"""Index Ripper UI using customtkinter with search, logs, and per-file downloads."""

# pylint: disable=too-many-lines
import json
import os
import posixpath
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event, Thread
from tkinter import filedialog, messagebox, ttk
from urllib.parse import unquote, urljoin, urlparse

import customtkinter as ctk
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend import Backend


class WebsiteCopier:
    """A GUI application for downloading files from a website directory listing."""

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )

    def __init__(self):
        """Initializes the main window and UI components."""
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.window = ctk.CTk()
        self.window.title("Index Ripper")
        self.window.geometry("1200x900")
        self.window.minsize(900, 650)

        self.backend = Backend(self)

        # Download control
        self.pause_event = Event()
        self.current_downloads = []

        # Add scan control
        self.scan_pause_event = Event()
        self.scan_pause_event.set()  # Initially set to not paused
        self.is_scanning = False

        # 添加线程锁，用于保护共享数据
        self.files_dict_lock = threading.Lock()
        self.folders_dict_lock = threading.Lock()

        # 初始化队列和处理状态
        self.dir_queue = Queue()
        self.file_queue = Queue()
        self.is_processing_dirs = False
        self.is_processing_files = False

        # --- Main Layout ---
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_rowconfigure(1, weight=1)

        # --- URL and filter area ---
        self.top_frame = ctk.CTkFrame(self.window)
        self.top_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        self.top_frame.grid_columnconfigure(0, weight=1)

        # URL input
        url_input_frame = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        url_input_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        url_input_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            url_input_frame, text="URL:", font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, padx=(0, 5))
        self.url_entry = ctk.CTkEntry(
            url_input_frame, placeholder_text="https://example.com"
        )
        self.url_entry.grid(row=0, column=1, sticky="ew")

        # Scan buttons
        scan_buttons_frame = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        scan_buttons_frame.grid(row=0, column=1, padx=10, pady=5)

        self.scan_btn = ctk.CTkButton(
            scan_buttons_frame, text="Scan", command=self.start_scan
        )
        self.scan_btn.pack(side="left", padx=5)

        self.scan_pause_btn = ctk.CTkButton(
            scan_buttons_frame,
            text="Pause Scan",
            command=self.toggle_scan_pause,
            state="disabled",
        )
        self.scan_pause_btn.pack(side="left", padx=5)

        self.clear_scan_btn = ctk.CTkButton(
            scan_buttons_frame, text="Clear", command=self.clear_scan_results
        )
        self.clear_scan_btn.pack(side="left", padx=5)

        # --- File type filter area ---
        filter_frame = ctk.CTkFrame(self.top_frame)
        filter_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
        filter_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            filter_frame, text="File Type Selection", font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, padx=10, pady=(5, 0), sticky="w")

        # File type checkbox container
        self.filter_checkboxes_frame = ctk.CTkScrollableFrame(
            filter_frame, label_text="", fg_color="transparent"
        )
        self.filter_checkboxes_frame.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        # Variable to store file types
        self.file_types = {}  # {'.pdf': BooleanVar(), '.jpg': BooleanVar(), ...}
        self.file_type_counts = {}  # {'.pdf': 0, '.jpg': 0, ...}

        # Select/deselect all buttons
        select_buttons_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        select_buttons_frame.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        ctk.CTkButton(
            select_buttons_frame, text="Select All", command=self.select_all_types
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            select_buttons_frame, text="Deselect All", command=self.deselect_all_types
        ).pack(side="left", padx=2)

        # --- File list area ---
        self.tree_frame = ctk.CTkFrame(self.window)
        self.tree_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.tree_frame.grid_rowconfigure(1, weight=1)
        self.tree_frame.grid_columnconfigure(0, weight=1)

        # Search bar
        search_frame = ctk.CTkFrame(self.tree_frame)
        search_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        search_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(search_frame, text="Search:").grid(row=0, column=0, padx=(5, 2))
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.on_search_filter_changed)
        self.search_entry = ctk.CTkEntry(
            search_frame, textvariable=self.search_var, state="disabled"
        )
        self.search_entry.grid(row=0, column=1, sticky="ew")
        self.full_tree_backup = {}

        # --- Treeview Styling ---
        style = ttk.Style()
        bg_color = self.window._apply_appearance_mode(
            ctk.ThemeManager.theme["CTkFrame"]["fg_color"]
        )
        text_color = self.window._apply_appearance_mode(
            ctk.ThemeManager.theme["CTkLabel"]["text_color"]
        )
        selected_color = self.window._apply_appearance_mode(
            ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        )

        style.theme_use("default")
        style.configure(
            "Treeview",
            background=bg_color,
            foreground=text_color,
            fieldbackground=bg_color,
            borderwidth=0,
            rowheight=22,
        )
        style.map("Treeview", background=[("selected", selected_color)])
        style.configure(
            "Treeview.Heading",
            background=self.window._apply_appearance_mode(
                ctk.ThemeManager.theme["CTkFrame"]["top_fg_color"]
            ),
            foreground=text_color,
            relief="flat",
            font=("Arial", 10, "bold"),
        )
        style.map(
            "Treeview.Heading",
            background=[
                (
                    "active",
                    self.window._apply_appearance_mode(
                        ctk.ThemeManager.theme["CTkButton"]["hover_color"]
                    ),
                )
            ],
        )

        self.tree = ttk.Treeview(
            self.tree_frame,
            selectmode="none",
            show=("tree", "headings"),
            style="Treeview",
        )

        self.tree.tag_configure("oddrow", background="#2B2B2B")
        self.tree.tag_configure("evenrow", background="#2E2E2E")
        self.tree.tag_configure("checked", foreground="#50C878")  # Emerald Green

        # Set column configuration
        self.tree["columns"] = ("size", "type")
        self.tree.heading("#0", text="Name", command=lambda: self.sort_tree("name"))
        self.tree.heading("size", text="Size", command=lambda: self.sort_tree("size"))
        self.tree.heading("type", text="Type", command=lambda: self.sort_tree("type"))

        self.tree.column("#0", minwidth=400, width=600)
        self.tree.column("size", width=120, anchor="center")
        self.tree.column("type", width=200, anchor="center")

        # Bind right-click menu
        self.tree.bind("<Button-3>", self.show_context_menu)

        # Create right-click menu (using tk.Menu as customtkinter doesn't have one)
        self.context_menu = tk.Menu(self.window, tearoff=0)
        self.context_menu.add_command(label="Select All", command=self.select_all)
        self.context_menu.add_command(label="Deselect All", command=self.deselect_all)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Expand All", command=self.expand_all)
        self.context_menu.add_command(label="Collapse All", command=self.collapse_all)

        # Sort status
        self.sort_column = None
        self.sort_reverse = False

        self.checked_items = set()
        self.checkbox_checked = "✔"
        self.folder_icon = "📁"
        self.file_icon = "📄"
        self.folders = {}

        self.scrollbar = ctk.CTkScrollbar(self.tree_frame, command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scrollbar.set)

        self.tree.grid(row=1, column=0, sticky="nsew")
        self.scrollbar.grid(row=1, column=1, sticky="ns")

        self.tree.bind("<Button-1>", self.on_tree_click)

        # --- Download control area ---
        control_frame = ctk.CTkFrame(self.window)
        control_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        self.download_btn = ctk.CTkButton(
            control_frame,
            text="Download Selected Files",
            command=self.download_selected,
        )
        self.download_btn.pack(side="left", padx=5, pady=5)

        self.pause_btn = ctk.CTkButton(
            control_frame,
            text="Pause Download",
            command=self.toggle_pause,
            state="disabled",
        )
        self.pause_btn.pack(side="left", padx=5, pady=5)

        self.path_btn = ctk.CTkButton(
            control_frame,
            text="Choose Download Location",
            command=self.choose_download_path,
        )
        self.path_btn.pack(side="left", padx=5, pady=5)

        # Thread download count control
        threads_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        threads_frame.pack(side="right", padx=5, pady=5)
        ctk.CTkLabel(threads_frame, text="Concurrent Downloads:").pack(side="left")
        self.threads_var = ctk.StringVar(value="5")
        threads_option_menu = ctk.CTkOptionMenu(
            threads_frame,
            values=[str(i) for i in range(1, 11)],
            variable=self.threads_var,
            command=self.update_thread_count,
        )
        threads_option_menu.pack(side="left", padx=5)

        # Toggle button to show/hide bottom panels (Downloads/Logs)
        self.panels_visible = False
        self.toggle_panels_btn = ctk.CTkButton(
            control_frame,
            text="Show Panels",
            width=110,
            command=self.toggle_panels,
        )
        self.toggle_panels_btn.pack(side="right", padx=5)

        # --- Progress bar ---
        self.progress_frame = ctk.CTkFrame(self.window)
        self.progress_frame.grid(row=3, column=0, padx=10, pady=(5, 10), sticky="ew")
        self.progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_var = ctk.DoubleVar()
        self.progress_bar = ctk.CTkProgressBar(
            self.progress_frame, variable=self.progress_var
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=0, padx=5, pady=2, sticky="ew")

        self.progress_label = ctk.CTkLabel(self.progress_frame, text="")
        self.progress_label.grid(row=1, column=0, padx=5, pady=2, sticky="w")

        # --- Panels (Downloads + Logs) inside a Tabview ---
        self.panels_tabview = ctk.CTkTabview(self.window)
        self.panels_tabview.grid(row=4, column=0, padx=10, pady=(0, 10), sticky="ew")

        self.panels_tabview.add("Downloads")
        self.panels_tabview.add("Logs")

        downloads_tab = self.panels_tabview.tab("Downloads")
        self.downloads_frame = ctk.CTkScrollableFrame(downloads_tab, label_text="")
        self.downloads_frame.pack(fill="x", expand=False)

        logs_tab = self.panels_tabview.tab("Logs")
        self.log_text = ctk.CTkTextbox(logs_tab, height=80)
        self.log_text.pack(fill="x", expand=False)
        self.log_text.configure(state="disabled")

        # Hide panels by default, can be restored from settings later
        self.panels_tabview.grid_remove()

        # Track per-file download UI elements and cancel events
        self.download_items = {}

        # Load and apply saved settings (panels visibility and active tab)
        self._settings_path = os.path.join(
            os.path.expanduser("~"),
            ".index_ripper_settings.json",
        )
        saved: dict = {}
        if os.path.exists(self._settings_path):
            try:
                with open(self._settings_path, "r", encoding="utf-8") as file_obj:
                    content = file_obj.read().strip()
                    saved = json.loads(content) if content else {}
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                saved = {}
        # Active tab
        active = saved.get("active_tab")
        if active in ("Downloads", "Logs"):
            try:
                self.panels_tabview.set(active)
            except tk.TclError:
                pass
        # Visibility
        visible = bool(saved.get("panels_visible", False))
        if visible:
            self.panels_tabview.grid()
            self.panels_visible = True
            self.toggle_panels_btn.configure(text="Hide Panels")
        else:
            self.panels_tabview.grid_remove()
            self.panels_visible = False
            self.toggle_panels_btn.configure(text="Show Panels")

        # Initialize session with retry
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 504],
        )

        self.files_dict = {}
        self.download_path = ""
        self.is_paused = False
        self.download_queue = Queue()
        self.max_workers = 5
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.active_downloads = []

        self.session = requests.Session()
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10,
            pool_block=False,
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.timeout = (10, 30)

        self.total_urls = 0
        self.scanned_urls = 0
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.should_stop = False

    def toggle_panels(self):
        """Show or hide the bottom panels (Downloads/Logs)."""
        if self.panels_visible:
            try:
                self.panels_tabview.grid_remove()
            except tk.TclError:
                pass
            self.panels_visible = False
            self.toggle_panels_btn.configure(text="Show Panels")
        else:
            try:
                self.panels_tabview.grid()
            except tk.TclError:
                pass
            self.panels_visible = True
            self.toggle_panels_btn.configure(text="Hide Panels")
        # Save setting
        # Persist setting (best-effort)
        data = {
            "panels_visible": bool(self.panels_visible),
            "active_tab": str(self.panels_tabview.get()),
        }
        try:
            with open(self._settings_path, "w", encoding="utf-8") as file_obj:
                json.dump(data, file_obj, ensure_ascii=False, indent=2)
        except OSError:
            # Ignore persistence errors
            pass

    def choose_download_path(self):
        """Opens a dialog to choose a download directory."""
        path = filedialog.askdirectory(title="Choose Download Location")
        if path:
            self.download_path = path
            self.path_btn.configure(text=f"Location: ...{path[-30:]}")

    def toggle_pause(self):
        """Pauses or resumes the download process."""
        if self.is_paused:
            self.pause_event.set()
            self.pause_btn.configure(text="Pause Download")
            self.is_paused = False
        else:
            self.pause_event.clear()
            self.pause_btn.configure(text="Resume Download")
            self.is_paused = True

    def toggle_scan_pause(self):
        """Toggle scan pause state"""
        if self.scan_pause_event.is_set():
            self.scan_pause_event.clear()
            self.scan_pause_btn.configure(text="Resume Scan")
            self.progress_label.configure(text="Scan paused")
        else:
            self.scan_pause_event.set()
            self.scan_pause_btn.configure(text="Pause Scan")

    def filter_file_type(self, file_name):
        """Check if file should be displayed"""
        ext = os.path.splitext(file_name)[1].lower()
        if not ext:
            ext = "(No Extension)"
        if ext.startswith("."):
            ext = ext[1:]
        ext = f".{ext}"

        existing_ext = next(
            (e for e in self.file_types if e.lower() == ext.lower()), None
        )

        return existing_ext is not None and self.file_types[existing_ext].get()

    def create_folder_structure(self, path, url):
        """Create folder structure and return ID of last folder"""
        path = unquote(path.replace("\\", "/"))
        path = posixpath.normpath(path).strip("/")

        if not path:
            return ""

        parts = path.split("/")
        current_path = ""
        parent = ""

        for part in parts:
            if not part:
                continue

            current_path = posixpath.join(current_path, part) if current_path else part

            with self.folders_dict_lock:
                if current_path in self.folders:
                    parent = self.folders[current_path]["id"]
                    continue

                # Check for existing folder by name under the same parent
                found = False
                for child in self.tree.get_children(parent):
                    child_text = self.tree.item(child)["text"]
                    child_tags = self.tree.item(child)["tags"]
                    if "folder" in child_tags:
                        # Extract folder name (remove icon)
                        folder_name = child_text.replace(f"{self.folder_icon} ", "")
                        if folder_name == part:
                            parent = child
                            self.folders[current_path] = {
                                "id": child,
                                "url": urljoin(url, current_path),
                                "full_path": current_path,
                            }
                            found = True
                            break
                if found:
                    continue

                folder_id = self.tree.insert(
                    parent,
                    "end",
                    text=f"{self.folder_icon} {part}",
                    values=("", "Directory"),
                    tags=("folder",),
                )
                self.folders[current_path] = {
                    "id": folder_id,
                    "url": urljoin(url, current_path),
                    "full_path": current_path,
                }
                parent = folder_id
        return parent

    def _get_ancestors(self, item):
        """Get all ancestor nodes of an item"""
        ancestors = []
        parent = self.tree.parent(item)
        while parent:
            ancestors.append(parent)
            parent = self.tree.parent(parent)
        return ancestors

    def on_tree_click(self, event):
        """Handle tree item click event."""
        item = self.tree.identify("item", event.x, event.y)
        if not item:
            return

        # Identify the specific element clicked
        element = self.tree.identify_element(event.x, event.y)

        # If the click is on the expand/collapse indicator, let the default
        # binding handle it and do nothing more.
        if "indicator" in element:
            return

        # If the click is on the cell (text/icon), toggle the check state.
        column = self.tree.identify_column(event.x)
        if column == "#0":  # Only toggle check if name column is clicked
            self.toggle_check(item)

    def toggle_check(self, item, force_check=None):
        """Toggle item checked status"""
        if not self.tree.exists(item):
            return

        tags = list(self.tree.item(item, "tags"))
        is_checked = "checked" in tags

        if force_check is not None:
            new_check_state = force_check
        else:
            new_check_state = not is_checked

        if new_check_state:
            if "checked" not in tags:
                tags.append("checked")
            self.checked_items.add(item)
        else:
            if "checked" in tags:
                tags.remove("checked")
            self.checked_items.discard(item)

        self.tree.item(item, tags=tuple(tags))

        if "folder" in self.tree.item(item, "tags"):
            for child in self.tree.get_children(item):
                self.toggle_check(child, force_check=new_check_state)

    def update_scan_progress(self):
        """Update scan progress"""
        if self.total_urls > 0:
            progress = self.scanned_urls / self.total_urls
            self.progress_bar.set(progress)
            self.progress_label.configure(
                text=f"Scanning... ({self.scanned_urls}/{self.total_urls}) {progress:.1%}"
            )
            self.window.update_idletasks()

    def process_dir_queue(self):
        """Processes the directory creation queue to avoid UI blocking."""
        try:
            if not hasattr(self, "dir_queue"):
                return
            self.is_processing_dirs = True
            if not self.dir_queue.empty():
                dir_path, url = self.dir_queue.get()
                self.create_folder_structure(dir_path, url)
                self.window.after(10, self.process_dir_queue)
            else:
                self.is_processing_dirs = False
        except tk.TclError as ex:
            self.is_processing_dirs = False
            print(f"Error processing directory queue (UI): {str(ex)}")

    def process_file_queue(self):
        """Processes the file queue to avoid UI blocking."""
        try:
            if not hasattr(self, "file_queue"):
                return
            self.is_processing_files = True
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
                self._safe_create_folder_and_add_file(
                    dir_path, url, file_name, size, file_type, full_path
                )
                self.window.after(5, self.process_file_queue)
            else:
                self.is_processing_files = False
        except tk.TclError as ex:
            self.is_processing_files = False
            print(f"Error processing file queue (UI): {str(ex)}")

    def _safe_create_folder_and_add_file(
        self, dir_path, url, file_name, size, file_type, full_path
    ):
        """Create folder structure and add file in main thread"""
        try:
            with self.files_dict_lock:
                if (
                    full_path in self.files_dict
                    and self.files_dict[full_path] is not None
                ):
                    return

            parent_id = self.create_folder_structure(dir_path, url)

            for child in self.tree.get_children(parent_id):
                if "file" in self.tree.item(child)["tags"]:
                    child_text = self.tree.item(child)["text"]
                    child_name = child_text.replace(f"{self.file_icon} ", "")
                    if child_name == file_name:
                        with self.files_dict_lock:
                            if full_path in self.files_dict:
                                del self.files_dict[full_path]
                        return

            self._add_file_to_tree(
                parent_id, file_name, size, file_type, full_path, url
            )
        except (tk.TclError, OSError) as ex:
            with self.files_dict_lock:
                if full_path in self.files_dict:
                    del self.files_dict[full_path]
            print(f"Error adding file to tree structure: {str(ex)}")

    def _add_file_to_tree(self, parent_id, file_name, size, file_type, full_path, url):
        """Add file to tree structure in main thread"""
        try:
            items_count = len(self.tree.get_children(parent_id))
            row_tag = "evenrow" if items_count % 2 == 0 else "oddrow"

            self.tree.insert(
                parent_id,
                "end",
                text=f"{self.file_icon} {file_name}",
                values=(size, file_type),
                tags=("file", row_tag),
            )
            with self.files_dict_lock:
                self.files_dict[full_path] = url
        except tk.TclError as ex:
            print(f"Error in _add_file_to_tree (TclError): {ex}")
        except RuntimeError as ex:
            print(f"Error in _add_file_to_tree (General): {ex}")

    def update_file_types(self, file_name):
        """Updates the file type filter UI."""
        ext = os.path.splitext(file_name)[1].lower()
        if not ext:
            ext = "(No Extension)"
        if ext.startswith("."):
            ext = ext[1:]
        ext = f".{ext}"

        if ext not in self.file_types:
            self.file_types[ext] = ctk.BooleanVar(value=False)
            self.file_type_counts[ext] = 0
            # Re-draw checkboxes
            self.redraw_file_type_filters()
        self.file_type_counts[ext] += 1
        # Update count on the checkbox
        for child in self.filter_checkboxes_frame.winfo_children():
            if child.cget("text").startswith(ext):
                # Use dict expansion to avoid type-checker complaints about unknown kwargs
                child.configure(**{"text": f"{ext} ({self.file_type_counts[ext]})"})
                break

    def redraw_file_type_filters(self):
        """Clears and redraws the file type filter checkboxes."""
        for widget in self.filter_checkboxes_frame.winfo_children():
            widget.destroy()

        sorted_types = sorted(self.file_types.keys())
        for i, file_type in enumerate(sorted_types):
            var = self.file_types[file_type]
            count = self.file_type_counts.get(file_type, 0)
            chk = ctk.CTkCheckBox(
                self.filter_checkboxes_frame,
                text=f"{file_type} ({count})",
                variable=var,
                command=self.apply_filters,
            )
            chk.grid(row=i // 4, column=i % 4, padx=5, pady=2, sticky="w")

    def apply_filters(self):
        """Applies selected file type filters by checking/unchecking items in the tree."""
        all_items = self.get_all_tree_items()
        items_to_expand = set()

        for item in all_items:
            tags = self.tree.item(item, "tags")
            if "file" in tags:
                text = self.tree.item(item, "text")
                file_name = text.replace(f"{self.file_icon} ", "")

                ext = os.path.splitext(file_name)[1].lower()
                if not ext:
                    ext = "(No Extension)"
                elif not ext.startswith("."):
                    ext = f".{ext}"

                if ext in self.file_types:
                    should_be_checked = self.file_types[ext].get()
                    self.toggle_check(item, force_check=should_be_checked)
                    if should_be_checked:
                        # If a file is checked, we need to expand its ancestors
                        parent = self.tree.parent(item)
                        while parent:
                            items_to_expand.add(parent)
                            parent = self.tree.parent(parent)

        for item_id in items_to_expand:
            self.tree.item(item_id, open=True)

    def get_all_tree_items(self, parent=""):
        """Recursively gets all item IDs from the treeview."""
        items = []
        for child in self.tree.get_children(parent):
            items.append(child)
            items.extend(self.get_all_tree_items(child))
        return items

    def select_all_types(self):
        """Selects all file type checkboxes."""
        for var in self.file_types.values():
            var.set(True)
        self.apply_filters()

    def deselect_all_types(self):
        """Deselects all file type checkboxes."""
        for var in self.file_types.values():
            var.set(False)
        self.apply_filters()

    def clear_scan_results(self):
        """Clears the treeview and all scan-related data."""
        if self.is_scanning:
            messagebox.showwarning(
                "Warning", "Cannot clear results while a scan is in progress."
            )
            return

        # Clear Treeview
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Clear data structures
        with self.files_dict_lock:
            self.files_dict.clear()
        with self.folders_dict_lock:
            self.folders.clear()

        self.checked_items.clear()
        self.file_types.clear()
        self.file_type_counts.clear()

        # Clear file type filter UI
        for widget in self.filter_checkboxes_frame.winfo_children():
            widget.destroy()

        # Reset scan progress
        self.total_urls = 0
        self.scanned_urls = 0
        self.progress_bar.set(0)
        self.progress_label.configure(text="Scan results cleared.")
        self.search_var.set("")
        self.search_entry.configure(state="disabled")
        self.full_tree_backup.clear()

    def on_search_filter_changed(self, *_):
        """Callback when the search entry text changes."""
        self.apply_search_filter()

    def apply_search_filter(self):
        """Filters the treeview based on the search query."""
        query = self.search_var.get().lower()

        # Detach all items first
        for item_id in self.full_tree_backup:
            if self.tree.exists(item_id):
                self.tree.detach(item_id)

        if not query:
            # If query is empty, reattach all items in their original order
            for item_id, data in self.full_tree_backup.items():
                if self.tree.exists(item_id):
                    self.tree.move(item_id, data["parent"], data["index"])
            return

        items_to_show = set()
        # Find items that match the query
        for item_id, data in self.full_tree_backup.items():
            if query in data["text"].lower():
                items_to_show.add(item_id)
                # Add all parents to ensure the path is visible
                parent = data["parent"]
                while parent:
                    items_to_show.add(parent)
                    parent = self.full_tree_backup[parent]["parent"]

        # Re-attach only the items that should be visible
        for item_id, data in self.full_tree_backup.items():
            if item_id in items_to_show:
                if self.tree.exists(item_id):
                    self.tree.move(item_id, data["parent"], data["index"])
                    if "folder" in data["tags"]:
                        self.tree.item(item_id, open=True)

    def update_thread_count(self, new_count_str: str):
        """Updates the number of concurrent download threads."""
        try:
            new_count = int(new_count_str)
            if 1 <= new_count <= 10:
                self.max_workers = new_count
                # Re-create the executor with the new worker count
                # Shut down the old one to release resources
                self.executor.shutdown(wait=False, cancel_futures=True)
                self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        except (ValueError, TypeError):
            pass

    def update_progress(self, file_path, file_name, progress):
        """Updates per-file or global progress from the main thread."""
        self.window.after(
            0, lambda: self._update_progress_ui(file_path, file_name, progress)
        )

    def _update_progress_ui(self, file_path, file_name, progress):
        """Update per-file progress if present; fallback to global bar."""
        item = self.download_items.get(file_path)
        if item:
            try:
                item["bar"].set(progress / 100)
                item["status"].configure(text=f"Downloading {progress:.1f}%")
            except tk.TclError:
                pass
        else:
            self.progress_bar.set(progress / 100)
            self.progress_label.configure(
                text=f"Downloading: {file_name} ({progress:.1f}%)"
            )

    def update_download_status(self, file_path, status_text):
        """Update status label for a specific download item."""
        item = self.download_items.get(file_path)
        if item:
            try:
                item["status"].configure(text=status_text)
            except tk.TclError:
                pass

    def log_message(self, message: str):
        """Append a message to the log panel."""
        try:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        except tk.TclError:
            pass

    def _ensure_download_item(self, file_path, file_name):
        """Create UI row for a download if not exists, and return cancel event."""
        if file_path in self.download_items:
            return self.download_items[file_path]["cancel_event"]

        row = ctk.CTkFrame(self.downloads_frame)
        row.pack(fill="x", padx=5, pady=4)

        name_label = ctk.CTkLabel(row, text=file_name)
        name_label.pack(side="left", padx=5)

        progress_bar_widget = ctk.CTkProgressBar(row)
        progress_bar_widget.set(0)
        progress_bar_widget.pack(side="left", expand=True, fill="x", padx=8)

        status = ctk.CTkLabel(row, text="Queued")
        status.pack(side="left", padx=5)

        cancel_event = threading.Event()

        def do_cancel():
            cancel_event.set()
            status.configure(text="Canceling...")

        cancel_btn = ctk.CTkButton(row, text="Cancel", width=80, command=do_cancel)
        cancel_btn.pack(side="right", padx=5)

        self.download_items[file_path] = {
            "frame": row,
            "bar": progress_bar_widget,
            "label": name_label,
            "status": status,
            "cancel_event": cancel_event,
        }
        return cancel_event

    def download_selected(self):
        """Download checked files"""
        if not self.checked_items:
            messagebox.showwarning("Warning", "Please select files to download")
            return

        files_to_download = [
            item
            for item in self.checked_items
            if "file" in self.tree.item(item)["tags"]
        ]

        if not files_to_download:
            messagebox.showwarning("Warning", "No files selected to download")
            return

        if not self.download_path:
            self.choose_download_path()
            if not self.download_path:  # User cancelled
                return

        self.pause_event.set()
        self.pause_btn.configure(state="normal")
        self.progress_label.configure(text="Preparing to download...")

        futures = []
        for item in files_to_download:
            text = self.tree.item(item)["text"]
            file_name = text.replace(f"{self.file_icon} ", "")

            path_parts = []
            current = item
            while current:
                parent = self.tree.parent(current)
                if not parent:
                    break
                parent_text = self.tree.item(parent)["text"]
                folder_name = parent_text.replace(f"{self.folder_icon} ", "")
                path_parts.append(folder_name)
                current = parent

            path_parts.reverse()
            relative_path = os.path.join(*path_parts)

            target_dir = os.path.join(self.download_path, relative_path)
            os.makedirs(target_dir, exist_ok=True)

            full_path_key = os.path.join(relative_path, file_name).replace("\\", "/")
            if full_path_key.startswith("/"):
                full_path_key = full_path_key[1:]

            url = self.files_dict.get(full_path_key)

            if url:
                file_path = os.path.join(target_dir, file_name)
                cancel_event = self._ensure_download_item(file_path, file_name)
                # Submit with cancel support and per-file progress
                future = self.executor.submit(
                    self.backend.download_file,
                    url,
                    file_path,
                    file_name,
                    cancel_event,
                )
                futures.append(future)

        threading.Thread(target=self.backend.monitor_downloads, args=(futures,)).start()

    def downloads_completed(self, completed, total):
        """Finalizes the download process and shows a summary."""
        self.progress_label.configure(
            text=f"Download completed: {completed}/{total} files."
        )
        self.pause_btn.configure(state="disabled")
        messagebox.showinfo(
            "Completed",
            f"{completed} of {total} selected files downloaded successfully.",
        )

    def start_scan(self):
        """Starts the website scanning process."""
        url = self.url_entry.get()
        if not url:
            messagebox.showerror("Error", "Please enter URL")
            return

        if self.is_scanning:
            self.backend.should_stop = True
            self.scan_btn.configure(text="Stopping...")
            self.scan_btn.configure(state="disabled")
            return

        self.backend.should_stop = False
        try:
            parsed_url = urlparse(url)
            site_name = parsed_url.netloc.replace(":", "_")
            self.download_path = os.path.join(os.getcwd(), site_name)
        except (OSError, TypeError) as ex:
            print(f"Error setting download path: {str(ex)}")
            self.download_path = os.path.join(os.getcwd(), "downloads")

        self.progress_label.configure(text="Preparing to scan...")
        self.scan_btn.configure(text="Stop Scan")
        self.search_entry.configure(state="disabled")
        self.search_var.set("")
        Thread(target=self.backend.scan_website, args=(url,)).start()

    def scan_completed(self):
        """Called by the backend when scanning is finished."""
        self.search_entry.configure(state="normal")
        self.full_tree_backup.clear()
        for item in self.get_all_tree_items():
            self.full_tree_backup[item] = {
                "parent": self.tree.parent(item),
                "index": self.tree.index(item),
                "text": self.tree.item(item, "text"),
                "tags": self.tree.item(item, "tags"),
            }

    def run(self):
        """Starts the Tkinter main loop."""
        self.window.mainloop()

    def show_context_menu(self, event):
        """Show right-click menu"""
        self.context_menu.post(event.x_root, event.y_root)

    def select_all(self):
        """Select all items"""
        for item in self.get_all_tree_items():
            self.toggle_check(item, force_check=True)

    def deselect_all(self):
        """Deselect all items"""
        for item in self.get_all_tree_items():
            self.toggle_check(item, force_check=False)

    def expand_all(self, parent=""):
        """Expand all nodes in the treeview."""
        for item in self.tree.get_children(parent):
            self.tree.item(item, open=True)
            self.expand_all(item)

    def collapse_all(self, parent=""):
        """Collapse all nodes in the treeview."""
        for item in self.tree.get_children(parent):
            self.tree.item(item, open=False)
            self.collapse_all(item)

    def on_closing(self):
        """Handles the window closing event."""
        # Persist settings on close (best-effort)
        data = {
            "panels_visible": bool(getattr(self, "panels_visible", False)),
            "active_tab": str(self.panels_tabview.get()),
        }
        settings_path = getattr(
            self,
            "_settings_path",
            os.path.join(os.path.expanduser("~"), ".index_ripper_settings.json"),
        )
        try:
            with open(settings_path, "w", encoding="utf-8") as file_obj:
                json.dump(data, file_obj, ensure_ascii=False, indent=2)
        except OSError:
            pass
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.backend.should_stop = True
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.window.destroy()

    def sort_tree(self, col):
        """Sorts the treeview columns."""
        items = [(self.tree.set(i, col), i) for i in self.tree.get_children("")]

        # A simple string sort
        items.sort(reverse=self.sort_reverse)

        for index, (_, i) in enumerate(items):
            self.tree.move(i, "", index)

        self.sort_reverse = not self.sort_reverse


if __name__ == "__main__":
    app = WebsiteCopier()
    app.run()
