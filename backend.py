"""
This module contains the backend logic for the Index Ripper application.
It handles scanning websites and downloading files.
"""

import concurrent.futures
import os
import socket
from queue import Queue
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app_utils import is_url_in_scope


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

    def _log(self, message):
        try:
            self.ui_manager.log_message(message)
        except AttributeError:
            print(message)

    def _notify(self, kind: str, title: str, message: str) -> None:
        if kind == "info":
            handler_name = "notify_info"
        elif kind == "error":
            handler_name = "notify_error"
        else:
            handler_name = "notify_warning"

        handler = getattr(self.ui_manager, handler_name, None)
        if callable(handler):
            try:
                handler(title, message)
                return
            except Exception:
                pass
        self._log(f"[{kind.upper()}] {title}: {message}")

    def _call_ui_hook(self, hook_name, **payload):
        hook = getattr(self.ui_manager, hook_name, None)
        if callable(hook):
            try:
                hook(**payload)
                return True
            except Exception as ex:
                self._log(f"[Hook] {hook_name} failed: {ex}")
                return False
        return False

    def scan_website(self, url):
        """Scans the website to find all files and directories."""
        try:
            self.ui_manager.is_scanning = True
            self._call_ui_hook("on_scan_started", url=url)

            all_urls = self._get_all_urls(url)
            self.ui_manager.total_urls = len(all_urls)
            self._call_ui_hook(
                "on_scan_progress",
                scanned_urls=self.ui_manager.scanned_urls,
                total_urls=self.ui_manager.total_urls,
            )

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
                    # Respect pause while consuming completed futures, to freeze progress bar
                    self.ui_manager.scan_pause_event.wait()
                    if self.should_stop:
                        # Cancel remaining futures
                        for future_item in futures:
                            if not future_item.done():
                                future_item.cancel()
                        break
                    try:
                        future.result()
                    except (
                        requests.RequestException,
                        socket.timeout,
                        concurrent.futures.CancelledError,
                    ) as ex:
                        # Log errors to UI log panel as well
                        try:
                            self.ui_manager.log_message(f"[Scan] Error: {str(ex)}")
                        except AttributeError:
                            pass
                    finally:
                        if self.ui_manager.is_scanning:
                            self.ui_manager.scanned_urls += 1
                            self._call_ui_hook(
                                "on_scan_progress",
                                scanned_urls=self.ui_manager.scanned_urls,
                                total_urls=self.ui_manager.total_urls,
                            )

            if not self.should_stop:
                if not self.ui_manager.files_dict:
                    self._notify("info", "Info", "No files found")
                else:
                    self._notify(
                        "info",
                        "Completed",
                        f"Scan completed, found {len(self.ui_manager.files_dict)} files",
                    )

        except (requests.RequestException, OSError) as ex:
            if self.ui_manager.is_scanning and not self.should_stop:
                self._notify("error", "Error", f"A network or OS error occurred: {str(ex)}")
        except RuntimeError as ex:
            if self.ui_manager.is_scanning and not self.should_stop:
                self._notify(
                    "error", "Error", f"An unknown error occurred during scan: {str(ex)}"
                )
        finally:
            self.ui_manager.is_scanning = False
            self.ui_manager.scan_pause_event.set()
            self._call_ui_hook("on_scan_finished", stopped=self.should_stop)

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
                link_text = link.get_text(strip=True)

                full_url = urljoin(url, href)
                if not full_url or not is_url_in_scope(base_url, full_url):
                    continue

                parsed_full = urlparse(full_url)
                path = parsed_full.path
                if not path:
                    path = "/"

                final_url = f"{parsed_full.scheme}://{parsed_full.netloc}{path}"

                is_directory_hint = href.endswith("/") or link_text.endswith("/")
                if is_directory_hint:
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
            self._log(f"[Scan] Error getting URL list for {url}: {str(ex)}")
            return []

    def _process_directory(self, url):
        """Process directory"""
        try:
            parsed_path = urlparse(url).path
            dir_path = parsed_path.rstrip("/")
            self._call_ui_hook(
                "on_scan_item", is_directory=True, path=dir_path, url=url
            )
        except (OSError, ValueError) as ex:
            self._log(f"[Scan] Error processing directory path {url}: {str(ex)}")

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

                self._call_ui_hook(
                    "on_scan_item",
                    is_directory=False,
                    path=dir_path,
                    url=url,
                    file_name=file_name,
                    size=size,
                    file_type=file_type,
                    full_path=full_path,
                )
            except (requests.RequestException, socket.timeout) as ex:
                self._log(f"[Scan] Could not process file {url}: {ex}")
                with self.ui_manager.files_dict_lock:
                    if full_path in self.ui_manager.files_dict:
                        del self.ui_manager.files_dict[full_path]
        except (OSError, ValueError) as ex:
            self._log(f"[Scan] Error processing file URL {url}: {str(ex)}")

    def download_file(self, url, file_path, file_name, cancel_event=None):
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
                    if cancel_event is not None and cancel_event.is_set():
                        self.ui_manager.log_message(f"[Download] Canceled: {file_name}")
                        try:
                            self.ui_manager.update_download_status(
                                file_path, "Canceled"
                            )
                        except AttributeError:
                            pass
                        return False
                    if self.should_stop:
                        self._log(f"[Download] Stopping download for {file_name}")
                        return False
                    if not data:
                        break
                    downloaded += len(data)
                    file_handle.write(data)

                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        self.ui_manager.update_progress(file_path, file_name, progress)

            self.ui_manager.update_progress(file_path, file_name, 100)
            try:
                self.ui_manager.update_download_status(file_path, "Completed")
            except AttributeError:
                pass
            return True

        except requests.exceptions.RequestException as ex:
            self._log(f"[Download] Error downloading {file_name}: {str(ex)}")
            try:
                self.ui_manager.update_download_status(file_path, "Failed")
                self.ui_manager.log_message(f"[Download] Error: {file_name} - {ex}")
            except AttributeError:
                pass
            return False
        except IOError as ex:
            self._log(f"[Download] File error for {file_name}: {str(ex)}")
            try:
                self.ui_manager.update_download_status(file_path, "Failed")
                self.ui_manager.log_message(
                    f"[Download] File error: {file_name} - {ex}"
                )
            except AttributeError:
                pass
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
                self._log(f"[Download] Error in future: {str(ex)}")
        self._call_ui_hook("on_downloads_finished", completed=completed, total=total)
