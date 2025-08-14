"""
This module contains the backend logic for the Index Ripper application.
It handles scanning websites and downloading files.
"""

import concurrent.futures
import os
import socket
from queue import Queue
from tkinter import messagebox
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


class Backend:
    """Handles the backend logic for scanning and downloading."""

    def __init__(self, ui_manager):
        """
        Initializes the Backend.

        Args:
            ui_manager: The UI instance (WebsiteCopier) to interact with.
        """
        self.ui_manager = ui_manager
        self.should_stop = False

    def scan_website(self, url):
        """Scans the website to find all files and directories."""
        try:
            self.ui_manager.is_scanning = True
            self.ui_manager.scan_pause_btn.configure(state="normal")
            self.ui_manager.progress_label.configure(text="Scanning website...")
            self.ui_manager.scan_btn.configure(state="disabled")

            if hasattr(self.ui_manager, "dir_queue"):
                while not self.ui_manager.dir_queue.empty():
                    self.ui_manager.dir_queue.get()
            if hasattr(self.ui_manager, "file_queue"):
                while not self.ui_manager.file_queue.empty():
                    self.ui_manager.file_queue.get()
            self.ui_manager.is_processing_dirs = False
            self.ui_manager.is_processing_files = False

            with self.ui_manager.files_dict_lock:
                self.ui_manager.files_dict.clear()
            with self.ui_manager.folders_dict_lock:
                self.ui_manager.folders.clear()

            self.ui_manager.tree.delete(*self.ui_manager.tree.get_children())
            self.ui_manager.file_types.clear()
            self.ui_manager.file_type_counts.clear()
            for widget in self.ui_manager.filter_checkboxes_frame.winfo_children():
                widget.destroy()

            self.ui_manager.total_urls = 0
            self.ui_manager.scanned_urls = 0

            all_urls = self._get_all_urls(url)
            self.ui_manager.total_urls = len(all_urls)

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                # Use a queue to manage tasks to allow for pausing
                task_queue = Queue()
                for url_info in all_urls:
                    task_queue.put(url_info)

                futures = []
                while not task_queue.empty():
                    if self.should_stop:
                        break
                    self.ui_manager.scan_pause_event.wait()  # Pause here

                    url_info = task_queue.get()
                    if url_info["is_directory"]:
                        futures.append(
                            executor.submit(self._process_directory, url_info["url"])
                        )
                    else:
                        futures.append(
                            executor.submit(self._process_file, url_info["url"])
                        )

                for future in concurrent.futures.as_completed(futures):
                    self.ui_manager.scan_pause_event.wait()  # Pause here as well
                    if self.should_stop:
                        # Cancel remaining futures
                        for f in futures:
                            if not f.done():
                                f.cancel()
                        break
                    try:
                        future.result()
                    except (
                        requests.RequestException,
                        socket.timeout,
                        concurrent.futures.CancelledError,
                    ) as ex:
                        print(f"Error processing URL: {str(ex)}")
                    finally:
                        if self.ui_manager.is_scanning:
                            self.ui_manager.scanned_urls += 1
                            self.ui_manager.update_scan_progress()

            if not self.should_stop:
                if not self.ui_manager.files_dict:
                    messagebox.showinfo("Info", "No files found")
                else:
                    messagebox.showinfo(
                        "Completed",
                        f"Scan completed, found {len(self.ui_manager.files_dict)} files",
                    )

        except (requests.RequestException, OSError) as ex:
            if self.ui_manager.is_scanning and not self.should_stop:
                messagebox.showerror(
                    "Error", f"A network or OS error occurred: {str(ex)}"
                )
        except RuntimeError as ex:
            if self.ui_manager.is_scanning and not self.should_stop:
                messagebox.showerror(
                    "Error", f"An unknown error occurred during scan: {str(ex)}"
                )
        finally:
            self.ui_manager.is_scanning = False
            self.ui_manager.scan_btn.configure(state="normal", text="Scan")
            self.ui_manager.scan_pause_btn.configure(state="disabled")
            self.ui_manager.scan_pause_event.set()
            self.ui_manager.progress_label.configure(text="")
            self.ui_manager.progress_bar.set(0)

    def _get_all_urls(self, url, scanned_urls=None, base_url=None):
        """Get all URLs that need to be processed"""
        if scanned_urls is None:
            scanned_urls = set()
            base_url = url

        if base_url is None:
            base_url = url

        parsed = urlparse(url)
        url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        normalized_url = url + "/" if url.endswith("/") else url

        if normalized_url in scanned_urls:
            return []

        scanned_urls.add(normalized_url)
        urls = []

        try:
            response = self.ui_manager.session.get(
                url,
                timeout=self.ui_manager.timeout,
                headers={"User-Agent": self.ui_manager.USER_AGENT},
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            unique_urls = set()

            for link in soup.find_all("a"):
                href = link.get("href")
                if not href or href in [".", "..", "/"] or href.startswith("?"):
                    continue

                full_url = urljoin(url, href)
                if not full_url or not full_url.startswith(base_url):
                    continue

                parsed_full = urlparse(full_url)
                path = parsed_full.path
                if not path:
                    path = "/"

                final_url = f"{parsed_full.scheme}://{parsed_full.netloc}{path}"

                if href.endswith("/"):
                    if not final_url.endswith("/"):
                        final_url += "/"
                else:
                    if final_url.endswith("/") and "." in os.path.basename(
                        final_url[:-1]
                    ):
                        final_url = final_url[:-1]

                if final_url in unique_urls or final_url in scanned_urls:
                    continue

                unique_urls.add(final_url)
                is_directory = final_url.endswith("/")
                url_info = {
                    "url": final_url,
                    "is_directory": is_directory,
                    "path": path,
                }
                urls.append(url_info)

                if is_directory and final_url not in scanned_urls:
                    urls.extend(self._get_all_urls(final_url, scanned_urls, base_url))
            return urls
        except (requests.RequestException, socket.timeout) as ex:
            print(f"Error getting URL list for {url}: {str(ex)}")
            return []

    def _process_directory(self, url):
        """Process directory"""
        try:
            parsed_path = urlparse(url).path
            dir_path = parsed_path.rstrip("/")
            with self.ui_manager.folders_dict_lock:
                if not hasattr(self.ui_manager, "dir_queue"):
                    self.ui_manager.dir_queue = Queue()
                self.ui_manager.dir_queue.put((dir_path, url))
            if not (
                hasattr(self.ui_manager, "is_processing_dirs")
                and self.ui_manager.is_processing_dirs
            ):
                self.ui_manager.process_dir_queue()
        except (OSError, ValueError) as ex:
            print(f"Error processing directory path {url}: {str(ex)}")

    def _process_file(self, url):
        """Process file"""
        try:
            parsed = urlparse(url)
            file_name = unquote(os.path.basename(parsed.path))
            dir_path = unquote(os.path.dirname(parsed.path))
            if not file_name:
                return

            full_path = os.path.join(dir_path, file_name).replace("\\", "/")
            if full_path.startswith("/"):
                full_path = full_path[1:]

            with self.ui_manager.files_dict_lock:
                if full_path in self.ui_manager.files_dict:
                    return
                self.ui_manager.files_dict[full_path] = None

            try:
                head = self.ui_manager.session.head(
                    url, timeout=(5, 10), allow_redirects=True
                )
                size_bytes = head.headers.get("content-length")
                size = (
                    f"{int(size_bytes) / 1024:.2f} KB"
                    if size_bytes and size_bytes.isdigit()
                    else "Unknown"
                )
                file_type = head.headers.get("content-type", "Unknown")

                with self.ui_manager.files_dict_lock:
                    if not hasattr(self.ui_manager, "file_queue"):
                        self.ui_manager.file_queue = Queue()
                    self.ui_manager.file_queue.put(
                        (dir_path, url, file_name, size, file_type, full_path)
                    )
                if (
                    not hasattr(self.ui_manager, "is_processing_files")
                    or not self.ui_manager.is_processing_files
                ):
                    self.ui_manager.window.after(0, self.ui_manager.process_file_queue)
            except (requests.RequestException, socket.timeout) as ex:
                print(f"Could not process file {url}: {ex}")
                with self.ui_manager.files_dict_lock:
                    if full_path in self.ui_manager.files_dict:
                        del self.ui_manager.files_dict[full_path]
        except (OSError, ValueError) as ex:
            print(f"Error processing file URL {url}: {str(ex)}")

    def download_file(self, url, file_path, file_name):
        """Downloads a single file."""
        try:
            response = self.ui_manager.session.get(
                url,
                stream=True,
                timeout=self.ui_manager.timeout,
                headers={"User-Agent": self.ui_manager.USER_AGENT},
            )
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            block_size = 8192
            downloaded = 0

            with open(file_path, "wb") as file_handle:
                for data in response.iter_content(block_size):
                    self.ui_manager.pause_event.wait()
                    if self.should_stop:
                        print(f"Stopping download for {file_name}")
                        return False
                    if not data:
                        break
                    downloaded += len(data)
                    file_handle.write(data)

                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        self.ui_manager.update_progress(file_name, progress)

            self.ui_manager.update_progress(file_name, 100)
            return True

        except requests.exceptions.RequestException as ex:
            print(f"Error downloading {file_name}: {str(ex)}")
            return False
        except IOError as ex:
            print(f"File error for {file_name}: {str(ex)}")
            return False

    def monitor_downloads(self, futures):
        """Monitors the download threads and updates the UI upon completion."""
        completed = 0
        total = len(futures)
        for future in concurrent.futures.as_completed(futures):
            try:
                if future.result():
                    completed += 1
            except (concurrent.futures.CancelledError, RuntimeError) as ex:
                print(f"Download error in future: {str(ex)}")

        self.ui_manager.window.after(
            0, self.ui_manager.downloads_completed, completed, total
        )
