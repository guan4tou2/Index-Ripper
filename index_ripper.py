import os
import mimetypes
import posixpath
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Thread, Event
from urllib.parse import urljoin, urlparse, unquote

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class WebsiteCopier:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Website File Downloader")
        self.window.geometry("1000x800")

        # Download control
        self.pause_event = Event()
        self.current_downloads = []

        # Add scan control
        self.scan_pause_event = Event()
        self.scan_pause_event.set()  # Initially set to not paused
        self.is_scanning = False

        # URL and filter area
        self.url_frame = ttk.LabelFrame(self.window, text="URL and Selection Settings")
        self.url_frame.pack(fill=tk.X, padx=5, pady=5)

        # URL input
        url_input_frame = ttk.Frame(self.url_frame)
        url_input_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(url_input_frame, text="URL:").pack(side=tk.LEFT)
        self.url_entry = ttk.Entry(url_input_frame)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Modify file type filter area
        filter_frame = ttk.LabelFrame(self.url_frame, text="File Type Selection")
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        # File type checkbox container
        self.filter_checkboxes_frame = ttk.Frame(filter_frame)
        self.filter_checkboxes_frame.pack(fill=tk.X, padx=5, pady=5)

        # Variable to store file types
        self.file_types = {}  # {'.pdf': BooleanVar(), '.jpg': BooleanVar(), ...}
        self.file_type_counts = {}  # {'.pdf': 0, '.jpg': 0, ...} Used to track file count for each type

        # Select/deselect all buttons
        select_buttons_frame = ttk.Frame(filter_frame)
        select_buttons_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(
            select_buttons_frame, text="Select All", command=self.select_all_types
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            select_buttons_frame, text="Deselect All", command=self.deselect_all_types
        ).pack(side=tk.LEFT, padx=2)

        # Modify scan button area
        scan_buttons_frame = ttk.Frame(self.url_frame)
        scan_buttons_frame.pack(pady=5)

        self.scan_btn = ttk.Button(
            scan_buttons_frame, text="Scan", command=self.start_scan
        )
        self.scan_btn.pack(side=tk.LEFT, padx=5)

        self.scan_pause_btn = ttk.Button(
            scan_buttons_frame,
            text="Pause Scan",
            command=self.toggle_scan_pause,
            state=tk.DISABLED,
        )
        self.scan_pause_btn.pack(side=tk.LEFT, padx=5)

        # File list area
        self.tree_frame = ttk.LabelFrame(self.window, text="File List")
        self.tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tree = ttk.Treeview(
            self.tree_frame,
            selectmode="none",
            show=("tree", "headings"),
            style="Custom.Treeview",  # Use custom style
        )

        # Modify custom style configuration
        style = ttk.Style()
        style.configure(
            "Custom.Treeview",
            rowheight=25,
            background="#2f3542",  # 深色背景
            fieldbackground="#2f3542",  # 保持一致的背景
            foreground="#ffffff",  # 白色文字
            borderwidth=1,
            relief="solid",
        )

        # Configure selected item background color
        style.map(
            "Custom.Treeview",
            background=[("selected", "#3742fa")],  # 深藍色選中背景
            foreground=[("selected", "#ffffff")],  # 選中時保持白色文字
        )

        # Add tag configuration - Modify priority order
        self.tree.tag_configure("unchecked", background="#2f3542")  # 基本背景
        self.tree.tag_configure("checked", background="#2ed573")  # 綠色選中背景
        self.tree.tag_configure("name_zone", background="#2f3542")  # 名稱區域
        self.tree.tag_configure("arrow_zone", background="#353b48")  # 箭頭區域
        self.tree.tag_configure("arrow_hover", background="#404859")  # 箭頭懸停效果
        self.tree.tag_configure("hidden", foreground="#747d8c")  # 隱藏項目使用灰色

        # Set table column title style
        style.configure(
            "Treeview.Heading",
            background="#353b48",  # 表頭背景色
            foreground="#ffffff",  # 表頭文字顏色
            relief="solid",
            borderwidth=1,
        )

        # Configure hover effect
        style.map(
            "Treeview.Heading",
            background=[("active", "#404859")],  # 表頭懸停效果
        )

        # Set alternating row colors
        self.tree.tag_configure("oddrow", background="#2f3542")  # 深色背景
        self.tree.tag_configure("evenrow", background="#353b48")  # 稍淺的深色背景

        # Set display mode (only use tree and headings)
        self.tree.configure(style="Custom.Treeview", show=("tree", "headings"))

        # Set column configuration
        self.tree["columns"] = ("size", "type")
        self.tree.heading("#0", text="Name", command=lambda: self.sort_tree("name"))
        self.tree.heading("size", text="Size", command=lambda: self.sort_tree("size"))
        self.tree.heading("type", text="Type", command=lambda: self.sort_tree("type"))

        # Set column width
        self.tree.column("#0", minwidth=300, width=400)
        self.tree.column("size", width=100)
        self.tree.column("type", width=150)

        # Bind right-click menu
        self.tree.bind("<Button-3>", self.show_context_menu)

        # Create right-click menu
        self.context_menu = tk.Menu(self.window, tearoff=0)
        self.context_menu.add_command(label="Select All", command=self.select_all)
        self.context_menu.add_command(label="Deselect All", command=self.deselect_all)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Expand All", command=self.expand_all)
        self.context_menu.add_command(label="Collapse All", command=self.collapse_all)

        # Sort status
        self.sort_column = None
        self.sort_reverse = False

        # Used to track checked status
        self.checked_items = set()

        # Modify checkbox icon
        self.checkbox_unchecked = ""  # Empty string, no unchecked box
        self.checkbox_checked = "✅"  # Checked
        self.folder_icon = "📁"  # Folder
        self.file_icon = "📄"  # File

        # Used to track folder structure
        self.folders = {}

        self.scrollbar = ttk.Scrollbar(
            self.tree_frame, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=self.scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Modify binding events
        self.tree.bind("<Button-1>", self.on_tree_click)

        # Download control area
        control_frame = ttk.Frame(self.window)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        self.download_btn = ttk.Button(
            control_frame,
            text="Download Selected Files",
            command=self.download_selected,
        )
        self.download_btn.pack(side=tk.LEFT, padx=5)

        self.pause_btn = ttk.Button(
            control_frame,
            text="Pause Download",
            command=self.toggle_pause,
            state=tk.DISABLED,
        )
        self.pause_btn.pack(side=tk.LEFT, padx=5)

        self.path_btn = ttk.Button(
            control_frame,
            text="Choose Download Location",
            command=self.choose_download_path,
        )
        self.path_btn.pack(side=tk.LEFT, padx=5)

        # Progress bar
        self.progress_frame = ttk.LabelFrame(self.window, text="Progress")
        self.progress_frame.pack(fill=tk.X, padx=5, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, variable=self.progress_var, maximum=100
        )
        self.progress_bar.pack(fill=tk.X, padx=5, pady=2)

        self.progress_label = ttk.Label(self.progress_frame, text="")
        self.progress_label.pack(pady=2)

        # Add new initial variables
        self.files_dict = {}
        self.download_path = ""  # Initialize as empty string
        self.is_paused = False
        self.download_queue = Queue()
        self.max_workers = 3  # Maximum files to download at once
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.active_downloads = []

        # Add download thread count control
        threads_frame = ttk.Frame(control_frame)
        threads_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(threads_frame, text="Concurrent Downloads:").pack(side=tk.LEFT)
        self.threads_var = tk.StringVar(value="3")
        threads_spinbox = ttk.Spinbox(
            threads_frame,
            from_=1,
            to=10,
            width=5,
            textvariable=self.threads_var,
            command=self.update_thread_count,
        )
        threads_spinbox.pack(side=tk.LEFT)

        # Configure requests session
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,  # Total retry count
            backoff_factor=1,  # Retry interval
            status_forcelist=[
                500,
                502,
                503,
                504,
            ],  # HTTP status codes that need to be retried
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,  # Connection pool size
            pool_maxsize=10,  # Maximum connections
            pool_block=False,  # Do not block when pool is full
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set longer timeout
        self.timeout = (10, 30)  # (Connection timeout, read timeout)

        # Add scan progress variables
        self.total_urls = 0
        self.scanned_urls = 0

        # Add window close event handling
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Add thread control
        self.should_stop = False

        # Bind mouse move and leave events
        self.tree.bind("<Motion>", self.on_mouse_move)
        self.tree.bind("<Leave>", self.on_mouse_leave)

    def choose_download_path(self):
        path = filedialog.askdirectory(title="Choose Download Location")
        if path:
            self.download_path = path

    def toggle_pause(self):
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
            self.progress_label.config(text="Scan paused")
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

        # Check if same file type exists (case insensitive)
        existing_ext = next(
            (e for e in self.file_types.keys() if e.lower() == ext.lower()), None
        )

        return existing_ext is not None and self.file_types[existing_ext].get()

    def create_folder_structure(self, path, url):
        """Create folder structure and return ID of last folder"""
        print("\n=== Starting Folder Structure Creation ===")
        print(f"Original path: {path}")
        print(f"Original URL: {url}")

        # Standardize path format and decode URL
        path = unquote(path.replace("\\", "/"))
        path = posixpath.normpath(path).strip("/")
        print(f"Standardized path: {path}")
        print(f"Existing folders: {list(self.folders.keys())}")

        if not path:
            return ""

        # Use full path as unique identifier
        parts = path.split("/")
        current_path = ""
        parent = ""

        for part in parts:
            if not part:  # Skip empty parts
                continue

            current_path = posixpath.join(current_path, part) if current_path else part
            print(f"\nProcessing folder: {part}")
            print(f"Current full path: {current_path}")

            # Check if full path already exists
            if current_path in self.folders:
                print(f"Found existing folder: {current_path}")
                parent = self.folders[current_path]["id"]
                continue

            print(f"Creating new folder: {current_path}")
            folder_id = self.tree.insert(
                parent,
                "end",
                text=f"{self.folder_icon} {part}",  # Remove unchecked box
                values=("", "Directory"),
                tags=("folder", "unchecked"),
            )
            self.folders[current_path] = {
                "id": folder_id,
                "url": urljoin(url, current_path),
                "full_path": current_path,
            }
            parent = folder_id

        print("\n=== Folder Structure Creation Completed ===")
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
        """Handle tree item click event"""
        print("\n=== Handling Click Event ===")
        item = self.tree.identify("item", event.x, event.y)
        if not item:
            return

        # Calculate click position
        item_x = int(self.tree.bbox(item)[0])
        relative_x = event.x - item_x

        # Define arrow area width
        arrow_width = 30

        print(f"Relative click position: {relative_x}")

        if relative_x < arrow_width:
            print("Clicked arrow area")
            # Default behavior for expanding/collapsing folder
            return
        else:
            print("Clicked item area")
            self.toggle_check(item)

    def toggle_check(self, item, force_check=None, force_uncheck=None):
        """Toggle item checked status"""
        print("\n=== Starting Toggle Check Status ===")
        print(f"Processing item ID: {item}")

        if not self.tree.exists(item):
            print("Error: Item does not exist")
            return

        # Get current item information
        current_item = self.tree.item(item)
        text = current_item["text"]
        tags = current_item["tags"]
        print(f"Current text: {text}")
        print(f"Current tags: {tags}")

        # Remove all checkboxes, keep only the last icon and name
        text_parts = text.split(" ")
        # Find the first icon (📁 or 📄) from the end
        for i, part in enumerate(text_parts):
            if part in [self.folder_icon, self.file_icon]:
                icon = part
                name = " ".join(text_parts[i + 1 :])
                break
        else:
            print(f"Error: No valid icon found - {text}")
            return

        is_checked = "checked" in tags

        # Decide new checked status
        if force_check is not None:
            is_checked = force_check
        elif force_uncheck is not None:
            is_checked = not force_uncheck
        else:
            is_checked = not is_checked

        # Update text and tags
        if is_checked:
            new_text = f"{self.checkbox_checked} {icon} {name}"
        else:
            new_text = f"{icon} {name}"

        new_tags = [tag for tag in tags if tag not in ("checked", "unchecked")]
        new_tags.append("checked" if is_checked else "unchecked")

        # Update item
        self.tree.item(item, text=new_text, tags=new_tags)

        # Update checked set
        if is_checked:
            self.checked_items.add(item)
        else:
            self.checked_items.discard(item)

        # If it's a folder, recursively process child items
        if "folder" in tags:
            for child in self.tree.get_children(item):
                self.toggle_check(child, force_check=is_checked)

        print("=== Toggle Check Status Completed ===\n")

    def scan_website(self, url):
        try:
            self.is_scanning = True
            self.scan_pause_btn.configure(state=tk.NORMAL)
            self.progress_label.config(text="Scanning website...")
            self.scan_btn.configure(state=tk.DISABLED)

            # Clear existing records
            self.folders.clear()
            self.tree.delete(*self.tree.get_children())
            self.files_dict.clear()

            # Reset scan progress
            self.total_urls = 0
            self.scanned_urls = 0

            # First get all URLs
            all_urls = self._get_all_urls(url)
            self.total_urls = len(all_urls)

            # Use thread pool to process URLs
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for url_info in all_urls:
                    if self.should_stop:  # Check if should stop
                        break

                    # Wait to continue scan
                    self.scan_pause_event.wait()

                    if url_info["is_directory"]:
                        futures.append(
                            executor.submit(self._process_directory, url_info["url"])
                        )
                    else:
                        futures.append(
                            executor.submit(self._process_file, url_info["url"])
                        )

                # Wait for all tasks to complete
                for future in futures:
                    if self.should_stop:  # Check if should stop
                        break
                    try:
                        future.result()
                    except Exception as e:
                        print(f"Error processing URL: {str(e)}")
                    finally:
                        if (
                            self.is_scanning
                        ):  # Update progress only when scan is not canceled
                            self.scanned_urls += 1
                            self._update_scan_progress()

            if not self.should_stop:  # Show result only when completed normally
                if not self.files_dict:
                    messagebox.showinfo("Info", "No files found")
                else:
                    messagebox.showinfo(
                        "Completed",
                        f"Scan completed, found {len(self.files_dict)} files",
                    )

        except Exception as e:
            if (
                self.is_scanning and not self.should_stop
            ):  # Show error only when scan is not canceled
                messagebox.showerror("Error", f"Unknown error occurred: {str(e)}")
        finally:
            self.is_scanning = False
            self.scan_btn.configure(state=tk.NORMAL, text="Scan")
            self.scan_pause_btn.configure(state=tk.DISABLED)
            self.scan_pause_event.set()  # Reset pause state
            self.progress_label.config(text="")

    def _print_file_list(self):
        """Output file list to console"""
        print("\n=== Scan Results ===")
        print(f"Found {len(self.files_dict)} files")
        print("\nFile List:")

        def print_item(item, level=0):
            item_text = self.tree.item(item)["text"]
            values = self.tree.item(item)["values"]
            tags = self.tree.item(item)["tags"]

            # Remove checkbox and icon, keep only name
            name = " ".join(item_text.split()[2:])

            # Add indentation based on level
            indent = "  " * level

            if "folder" in tags:
                print(f"{indent}📁 {name}/")
                # Recursively output child items
                for child in self.tree.get_children(item):
                    print_item(child, level + 1)
            else:
                size = values[0] if values else "Unknown"
                file_type = values[1] if len(values) > 1 else "Unknown"
                print(f"{indent}📄 {name} ({size}, {file_type})")

        # Start from root node
        for item in self.tree.get_children():
            print_item(item)

        print("\n=== End ===\n")

    def _get_all_urls(self, url, scanned_urls=None, base_url=None):
        """Get all URLs that need to be processed"""
        if scanned_urls is None:
            scanned_urls = set()
            base_url = url

        if url in scanned_urls:
            return []

        scanned_urls.add(url)
        urls = []

        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                },
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Use set to remove duplicates
            unique_urls = set()

            for link in soup.find_all("a"):
                href = link.get("href")
                if not href or href in [".", "..", "/"] or href.startswith("?"):
                    continue

                full_url = urljoin(url, href)
                if not base_url[:-1] in full_url:
                    continue

                parsed = urlparse(full_url)
                normalized_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

                # Standardize path
                path = parsed.path.rstrip("/")
                if not path:
                    continue

                # If URL has been processed, skip
                if normalized_url in unique_urls:
                    continue

                unique_urls.add(normalized_url)

                is_directory = href.endswith("/")
                url_info = {
                    "url": normalized_url,
                    "is_directory": is_directory,
                    "path": path,
                }

                urls.append(url_info)

                # If it's a directory and not scanned, recursively process
                if is_directory and normalized_url not in scanned_urls:
                    urls.extend(
                        self._get_all_urls(normalized_url, scanned_urls, base_url)
                    )

            return urls

        except Exception as e:
            print(f"Error getting URL list: {str(e)}")
            return []

    def _update_scan_progress(self):
        """Update scan progress"""
        if self.total_urls > 0:
            progress = (self.scanned_urls / self.total_urls) * 100
            self.progress_var.set(progress)
            self.progress_label.config(
                text=f"Scan progress... ({self.scanned_urls}/{self.total_urls}) {progress:.1f}%"
            )
            self.window.update_idletasks()

    def _process_directory(self, url):
        """Process directory"""
        try:
            parsed_path = urlparse(url).path
            dir_path = parsed_path.rstrip("/")
            self.create_folder_structure(dir_path, url)
        except Exception as e:
            print(f"Error processing directory: {str(e)}")

    def _process_file(self, url):
        """Process file"""
        try:
            print("\n=== Starting File Processing ===")
            print(f"Processing URL: {url}")

            parsed = urlparse(url)
            file_name = unquote(os.path.basename(parsed.path))
            dir_path = unquote(os.path.dirname(parsed.path))

            print(f"File name: {file_name}")
            print(f"Directory path: {dir_path}")

            if not file_name:
                return

            # Standardize path
            full_path = os.path.join(dir_path, file_name).replace("\\", "/")
            if full_path.startswith("/"):
                full_path = full_path[1:]

            print(f"Full path: {full_path}")

            # Check if file already exists
            if full_path in self.files_dict:
                print(f"File already exists: {full_path}")
                return

            try:
                head = self.session.head(url, timeout=(5, 10), allow_redirects=True)

                size = head.headers.get("content-length", "Unknown")
                if size != "Unknown":
                    size = f"{int(size) / 1024:.2f} KB"

                file_type = head.headers.get("content-type", "Unknown")

                # First update file type list
                self.window.after(0, lambda: self.update_file_types(file_name))

                # Create folder structure and add file in main thread
                self.window.after(
                    0,
                    lambda: self._safe_create_folder_and_add_file(
                        dir_path, url, file_name, size, file_type, full_path
                    ),
                )

            except (requests.RequestException, socket.timeout):
                pass

        except Exception as e:
            print(f"Error processing file: {str(e)}")

    def _safe_create_folder_and_add_file(
        self, dir_path, url, file_name, size, file_type, full_path
    ):
        """Create folder structure and add file in main thread"""
        try:
            parent_id = self.create_folder_structure(dir_path, url)
            self._add_file_to_tree(
                parent_id, file_name, size, file_type, full_path, url
            )
        except Exception as e:
            print(f"Error adding file to tree structure: {str(e)}")

    def _add_file_to_tree(self, parent_id, file_name, size, file_type, full_path, url):
        """Add file to tree structure in main thread"""
        try:
            # Get current number of items to determine odd/even row
            items_count = len(self.tree.get_children(parent_id))
            row_tags = ["evenrow"] if items_count % 2 == 0 else ["oddrow"]

            # Add file without unchecked box
            item_id = self.tree.insert(
                parent_id,
                "end",
                text=f"{self.file_icon} {file_name}",
                values=(size, file_type),
                tags=("file", "unchecked") + tuple(row_tags),
            )
            self.files_dict[full_path] = url

            # Add file item to corresponding file type set
            ext = os.path.splitext(file_name)[1].lower()
            if not ext:
                ext = "(No Extension)"
            if ext.startswith("."):
                ext = ext[1:]
            ext = f".{ext}"

            if hasattr(self, "_type_files"):
                if ext not in self._type_files:
                    self._type_files[ext] = set()
                self._type_files[ext].add(item_id)

            # Ensure parent folder is expanded
            current = parent_id
            while current:
                self.tree.item(current, open=True)
                current = self.tree.parent(current)

        except Exception as e:
            print(f"Error adding file to tree structure: {str(e)}")

    def update_thread_count(self):
        try:
            new_count = int(self.threads_var.get())
            self.executor._max_workers = new_count
            self.max_workers = new_count
        except ValueError:
            pass

    def download_file(self, url, file_path, file_name):
        try:
            response = self.session.get(
                url,
                stream=True,
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                },
            )
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            block_size = 8192
            downloaded = 0

            with open(file_path, "wb") as f:
                for data in response.iter_content(block_size):
                    if not self.pause_event.is_set():
                        continue
                    if not data:
                        break
                    downloaded += len(data)
                    f.write(data)

                    if downloaded % (block_size * 10) == 0:
                        progress = (downloaded / total_size) * 100
                        self.update_progress(file_name, progress)

            self.update_progress(file_name, 100)
            return True

        except requests.exceptions.RequestException as e:
            error_msg = "Network error"
            if isinstance(e, requests.exceptions.ConnectTimeout):
                error_msg = "Connection timeout"
            elif isinstance(e, requests.exceptions.ConnectionError):
                error_msg = "Connection failed"
            elif isinstance(e, requests.exceptions.ReadTimeout):
                error_msg = "Read timeout"

            messagebox.showerror(
                "Error", f"Error downloading {file_name}: {error_msg}: {str(e)}"
            )
            return False

    def update_progress(self, file_name, progress):
        self.window.after(0, lambda: self._update_progress(file_name, progress))

    def _update_progress(self, file_name, progress):
        self.progress_var.set(progress)
        self.progress_label.config(text=f"Downloading: {file_name} ({progress:.1f}%)")

    def download_selected(self):
        """Download checked files"""
        if not self.checked_items:
            messagebox.showwarning("Warning", "Please select files to download")
            return

        # Filter out folders, only download files
        files_to_download = [
            item
            for item in self.checked_items
            if "file" in self.tree.item(item)["tags"]
        ]

        if not files_to_download:
            messagebox.showwarning("Warning", "Please select files to download")
            return

        # If no download path selected, use default
        if not self.download_path:
            self.download_path = os.path.join(os.getcwd(), "downloads")

        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)

        self.pause_event.set()
        self.pause_btn.configure(state=tk.NORMAL)

        # Switch to download progress display
        self.progress_frame.configure(text="Download Progress")
        self.progress_var.set(0)
        self.progress_label.config(text="Preparing to download...")

        # Create download tasks
        futures = []
        for item in files_to_download:
            # Get file name (remove checkbox and icon)
            text_parts = self.tree.item(item)["text"].split(" ")
            for i, part in enumerate(text_parts):
                if part in [self.folder_icon, self.file_icon]:
                    file_name = " ".join(text_parts[i + 1 :])
                    break
            else:
                continue

            # Build full path for file
            path_parts = []
            current = item
            while current:
                parent_text = self.tree.item(current)["text"]
                # Also process text for parent items to get pure name
                for i, part in enumerate(parent_text.split(" ")):
                    if part in [self.folder_icon, self.file_icon]:
                        if current != item:  # Exclude file name
                            folder_name = " ".join(parent_text.split(" ")[i + 1 :])
                            path_parts.append(folder_name)
                        break
                current = self.tree.parent(current)

            # Reverse path parts and combine
            path_parts.reverse()
            relative_path = os.path.join(*path_parts) if path_parts else ""

            # Create target directory
            target_dir = os.path.join(self.download_path, relative_path)
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)

            # Get download URL
            full_path = os.path.join(relative_path, file_name).replace("\\", "/")
            url = self.files_dict.get(full_path)

            if url:
                file_path = os.path.join(target_dir, file_name)
                future = self.executor.submit(
                    self.download_file, url, file_path, file_name
                )
                futures.append(future)

        # Monitor download progress thread
        def monitor_downloads():
            completed = 0
            total = len(futures)
            for future in futures:
                try:
                    if future.result():
                        completed += 1
                        # Update total progress
                        progress = (completed / total) * 100
                        self.window.after(
                            0, lambda p=progress: self.progress_var.set(p)
                        )
                except Exception as e:
                    print(f"Download error: {str(e)}")

            self.window.after(0, lambda: self._downloads_completed())

        threading.Thread(target=monitor_downloads).start()

    def _downloads_completed(self):
        self.progress_label.config(text="Download completed")
        self.pause_btn.configure(state=tk.DISABLED)
        messagebox.showinfo("Completed", "Selected files downloaded successfully")

    def start_scan(self):
        url = self.url_entry.get()
        if not url:
            messagebox.showerror("Error", "Please enter URL")
            return

        # Set download path to website name
        try:
            parsed_url = urlparse(url)
            site_name = parsed_url.netloc.split(":")[0]  # Remove possible port number
            self.download_path = os.path.join(os.getcwd(), site_name)
        except Exception as e:
            print(f"Error setting download path: {str(e)}")
            self.download_path = os.path.join(os.getcwd(), "downloads")

        # If scanning, cancel scan
        if self.is_scanning:
            self.is_scanning = False
            self.scan_btn.configure(text="Scan")
            return

        # Reset progress bar and text
        self.progress_frame.configure(text="Scan Progress")
        self.progress_var.set(0)
        self.progress_label.config(text="Preparing to scan...")

        self.scan_btn.configure(text="Stop Scan")
        Thread(target=self.scan_website, args=(url,)).start()

    def run(self):
        self.window.mainloop()

    def show_context_menu(self, event):
        """Show right-click menu"""
        self.context_menu.post(event.x_root, event.y_root)

    def select_all(self):
        """Select all items"""

        def check_all(parent=""):
            for item in self.tree.get_children(parent):
                self.toggle_check(item, force_check=True)
                if self.tree.get_children(item):  # If there are child items
                    check_all(item)

        check_all()

    def deselect_all(self):
        """Deselect all"""

        def uncheck_all(parent=""):
            for item in self.tree.get_children(parent):
                self.toggle_check(item, force_uncheck=True)
                if self.tree.get_children(item):
                    uncheck_all(item)

        uncheck_all()

    def expand_all(self):
        """Expand all folders"""

        def expand(parent=""):
            for item in self.tree.get_children(parent):
                if "folder" in self.tree.item(item)["tags"]:
                    # Keep original tags and checked status
                    current_tags = self.tree.item(item)["tags"]
                    self.tree.item(item, open=True, tags=current_tags)
                expand(item)

        expand()

    def collapse_all(self):
        """Collapse all folders"""

        def collapse(parent=""):
            for item in self.tree.get_children(parent):
                if "folder" in self.tree.item(item)["tags"]:
                    # Keep original tags and checked status
                    current_tags = self.tree.item(item)["tags"]
                    self.tree.item(item, open=False, tags=current_tags)
                collapse(item)

        collapse()

    def sort_tree(self, column):
        """Sort tree structure"""
        # If clicked on same column, switch sort order
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_reverse = False
            self.sort_column = column

        def get_sort_key(item):
            if column == "name":
                return self.tree.item(item)["text"].lower()
            elif column == "size":
                size = self.tree.item(item)["values"][0]
                try:
                    return float(size.split()[0])
                except (ValueError, IndexError, AttributeError):
                    return 0
            else:
                return self.tree.item(item)["values"][1].lower()

        # Sort folders and files separately
        def sort_level(parent=""):
            items = self.tree.get_children(parent)
            # Separate folders and files
            folders = [
                item for item in items if "folder" in self.tree.item(item)["tags"]
            ]
            files = [item for item in items if "file" in self.tree.item(item)["tags"]]

            # Sort folders and files
            sorted_folders = sorted(
                folders, key=get_sort_key, reverse=self.sort_reverse
            )
            sorted_files = sorted(files, key=get_sort_key, reverse=self.sort_reverse)

            # Re-arrange items
            for idx, item in enumerate(sorted_folders + sorted_files):
                self.tree.move(item, parent, idx)
                # Recursively sort child items
                if self.tree.get_children(item):
                    sort_level(item)

        sort_level()

    def on_closing(self):
        """Handle window close event"""
        self.should_stop = True
        self.is_scanning = False

        # Wait for all threads to complete
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=False)

        self.window.destroy()
        os._exit(0)  # Force terminate all threads

    def update_file_types(self, file_name):
        """Update file type list"""
        ext = os.path.splitext(file_name)[1].lower()
        if not ext:
            ext = "(No Extension)"

        # Standardize file type
        if ext.startswith("."):
            ext = ext[1:]  # Remove leading dot
        ext = f".{ext}"  # Ensure leading dot

        # Check if same file type exists (case insensitive)
        existing_ext = next(
            (e for e in self.file_types.keys() if e.lower() == ext.lower()), None
        )

        if existing_ext:
            ext = existing_ext  # Use existing case form
            self.file_type_counts[ext] += 1
            # Update checkbox text
            self.window.after(0, lambda: self._update_type_label(ext))
        else:
            # Create new file type
            self.file_types[ext] = tk.BooleanVar(value=False)
            self.file_type_counts[ext] = 1
            if not hasattr(self, "_type_files"):
                self._type_files = {}
            self._type_files[ext] = set()
            # Add new checkbox in UI
            self.window.after(0, lambda: self._add_type_checkbox(ext))

    def _add_type_checkbox(self, ext):
        """Add file type checkbox"""
        frame = ttk.Frame(self.filter_checkboxes_frame)
        frame.pack(side=tk.LEFT, padx=2)

        # Create checkbox and bind selection event
        cb = ttk.Checkbutton(
            frame,
            text=f"{ext} ({self.file_type_counts[ext]})",
            variable=self.file_types[ext],
            command=lambda: self._on_type_selected(ext),
        )
        cb.pack(side=tk.LEFT)

        # Save checkbox reference for updating
        if not hasattr(self, "_type_checkboxes"):
            self._type_checkboxes = {}
        self._type_checkboxes[ext] = cb

    def _on_type_selected(self, ext):
        """Handle file type selection event"""
        is_selected = self.file_types[ext].get()

        # Update selection status for all related files
        if hasattr(self, "_type_files") and ext in self._type_files:
            for item in self._type_files[ext]:
                if self.tree.exists(item):
                    if is_selected:
                        # Use toggle_check to set selected status
                        self.toggle_check(item, force_check=True)
                        # Expand to path of that file
                        self._expand_to_item(item)
                    else:
                        # Use toggle_check to set unselected status
                        self.toggle_check(item, force_uncheck=True)

        # Update file visibility
        self.refresh_file_list()

    def _update_type_label(self, ext):
        """Update file type checkbox text"""
        if hasattr(self, "_type_checkboxes") and ext in self._type_checkboxes:
            self._type_checkboxes[ext].configure(
                text=f"{ext} ({self.file_type_counts[ext]})"
            )

    def select_all_types(self):
        """Select all file types"""
        # Set all file types to selected
        for ext, var in self.file_types.items():
            var.set(True)
            # Select all files of that type
            if hasattr(self, "_type_files") and ext in self._type_files:
                for item in self._type_files[ext]:
                    if self.tree.exists(item):
                        self.toggle_check(item, force_check=True)

        # Update file visibility
        self.refresh_file_list()

    def deselect_all_types(self):
        """Deselect all file types"""
        # Set all file types to unselected
        for ext, var in self.file_types.items():
            var.set(False)
            # Deselect all files of that type
            if hasattr(self, "_type_files") and ext in self._type_files:
                for item in self._type_files[ext]:
                    if self.tree.exists(item):
                        self.toggle_check(item, force_uncheck=True)

        # Update file visibility
        self.refresh_file_list()

    def refresh_file_list(self):
        """Re-filter file list based on selected file types"""
        for idx, item in enumerate(self.tree.get_children()):
            row_tags = ["evenrow"] if idx % 2 == 0 else ["oddrow"]
            current_tags = list(self.tree.item(item)["tags"])
            # Keep important tags but update row color tag
            base_tags = [
                tag for tag in current_tags if tag not in ("evenrow", "oddrow")
            ]
            self.tree.item(item, tags=base_tags + row_tags)
            self._refresh_item_visibility(item)

    def _refresh_item_visibility(self, item):
        """Recursively update item visibility"""
        if not self.tree.exists(item):
            return False

        is_folder = "folder" in self.tree.item(item)["tags"]
        current_tags = list(self.tree.item(item)["tags"])

        # Keep important tags
        base_tags = [
            tag
            for tag in current_tags
            if tag
            in (
                "checked",
                "unchecked",
                "file",
                "folder",
                "arrow_hover",
                "arrow_zone",
                "name_zone",
            )
        ]

        if is_folder:
            # Recursively process child items
            has_visible_children = False
            for child in self.tree.get_children(item):
                if self._refresh_item_visibility(child):
                    has_visible_children = True

            # If folder has visible child items, show folder
            if has_visible_children:
                self.tree.item(item, tags=base_tags)
                return True
            else:
                self.tree.item(item, tags=base_tags + ["hidden"])
                return False
        else:
            # Check if file type is selected
            file_name = " ".join(self.tree.item(item)["text"].split()[2:])

            ext = os.path.splitext(file_name)[1].lower()
            if not ext:
                ext = "(No Extension)"
            if ext.startswith("."):
                ext = ext[1:]
            ext = f".{ext}"

            if ext in self.file_types and self.file_types[ext].get():
                self.tree.item(item, tags=base_tags)
                return True
            else:
                self.tree.item(item, tags=base_tags + ["hidden"])
                return False

    def _expand_to_item(self, item):
        """Expand to specified item path"""
        parent = self.tree.parent(item)
        while parent:
            self.tree.item(parent, open=True)
            parent = self.tree.parent(parent)

    def setup_tree(self):
        """Set up file tree"""
        print("\n=== Initializing Tree ===")

        # Set up tree frame
        self.tree_frame = ttk.Frame(self.window)
        self.tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Custom tree style
        style = ttk.Style()
        style.configure(
            "Custom.Treeview",
            indent=30,
            background="#ffffff",
            fieldbackground="#ffffff",
        )

        # Set up tree and scrollbar
        self.tree = ttk.Treeview(
            self.tree_frame,
            columns=("size", "type"),
            selectmode="none",
            style="Custom.Treeview",
        )

        # Set up different area labels and styles
        self.tree.tag_configure("arrow_zone", background="#f0f0f0")  # Arrow area
        self.tree.tag_configure("checkbox_zone", background="#e8e8e8")  # Checkbox area
        self.tree.tag_configure("name_zone", background="#ffffff")  # Name area

        # Bind mouse move event to show area
        self.tree.bind("<Motion>", self.on_mouse_move)
        self.tree.bind("<Button-1>", self.on_tree_click)

        # Set column titles
        self.tree.heading("#0", text="Name")
        self.tree.heading("size", text="Size")
        self.tree.heading("type", text="Type")

        # Set column width
        self.tree.column("#0", width=400, minwidth=200)
        self.tree.column("size", width=100)
        self.tree.column("type", width=100)

        print("Tree setup completed")

    def on_mouse_move(self, event):
        """Handle mouse move event"""
        item = self.tree.identify("item", event.x, event.y)
        if not item:
            return

        # Clear all item hover effects
        self._clear_hover_effects()

        # Set background color based on mouse position
        region = self.tree.identify("region", event.x, event.y)
        if region == "tree":
            # Calculate different area x coordinate ranges
            item_x = int(self.tree.bbox(item)[0])  # Item start x coordinate
            arrow_width = 30  # Arrow area width

            # Get current item tags
            current_tags = list(self.tree.item(item)["tags"])
            base_tags = [
                tag
                for tag in current_tags
                if tag in ("checked", "unchecked", "file", "folder")
            ]

            if event.x < item_x + arrow_width:
                # Check if it's a folder (has child items)
                if self.tree.get_children(item):
                    self.tree.item(item, tags=base_tags + ["arrow_hover"])
                    self.tree.configure(cursor="hand2")
                else:
                    self.tree.item(item, tags=base_tags + ["arrow_zone"])
                    self.tree.configure(cursor="")
            else:
                self.tree.item(item, tags=base_tags + ["name_zone"])
                self.tree.configure(cursor="")

    def on_mouse_leave(self, event):
        """Handle mouse leave event"""
        self._clear_hover_effects()
        self.tree.configure(cursor="")

    def _clear_hover_effects(self):
        """Clear all hover effects"""
        for item in self.tree.get_children(""):
            self._clear_item_hover(item)

    def _clear_item_hover(self, item):
        """Clear single item hover effects"""
        if not self.tree.exists(item):
            return

        current_tags = list(self.tree.item(item)["tags"])
        # Keep basic tags
        base_tags = [
            tag
            for tag in current_tags
            if tag in ("checked", "unchecked", "file", "folder")
        ]
        self.tree.item(item, tags=base_tags)

        # Recursively process child items
        for child in self.tree.get_children(item):
            self._clear_item_hover(child)


if __name__ == "__main__":
    app = WebsiteCopier()
    app.run()
