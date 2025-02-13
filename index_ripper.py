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
        self.window.title("網站檔案下載器")
        self.window.geometry("1000x800")

        # 下載控制
        self.pause_event = Event()
        self.current_downloads = []

        # 添加掃描控制
        self.scan_pause_event = Event()
        self.scan_pause_event.set()  # 初始設置為未暫停
        self.is_scanning = False

        # URL和過濾區域
        self.url_frame = ttk.LabelFrame(self.window, text="網址和過濾設置")
        self.url_frame.pack(fill=tk.X, padx=5, pady=5)

        # URL輸入
        url_input_frame = ttk.Frame(self.url_frame)
        url_input_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(url_input_frame, text="網址:").pack(side=tk.LEFT)
        self.url_entry = ttk.Entry(url_input_frame)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)


        # 修改檔案類型過濾區域
        filter_frame = ttk.LabelFrame(self.url_frame, text="檔案類型過濾")
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        # 檔案類型勾選框容器
        self.filter_checkboxes_frame = ttk.Frame(filter_frame)
        self.filter_checkboxes_frame.pack(fill=tk.X, padx=5, pady=5)

        # 用於存儲檔案類型的變數
        self.file_types = {}  # {'.pdf': BooleanVar(), '.jpg': BooleanVar(), ...}
        self.file_type_counts = {}  # {'.pdf': 0, '.jpg': 0, ...} 用於記錄每種類型的檔案數量

        # 全選/取消全選按鈕
        select_buttons_frame = ttk.Frame(filter_frame)
        select_buttons_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(
            select_buttons_frame, text="全選", command=self.select_all_types
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            select_buttons_frame, text="取消全選", command=self.deselect_all_types
        ).pack(side=tk.LEFT, padx=2)

        # 修改掃描按鈕區域
        scan_buttons_frame = ttk.Frame(self.url_frame)
        scan_buttons_frame.pack(pady=5)

        self.scan_btn = ttk.Button(
            scan_buttons_frame, text="掃描", command=self.start_scan
        )
        self.scan_btn.pack(side=tk.LEFT, padx=5)

        self.scan_pause_btn = ttk.Button(
            scan_buttons_frame,
            text="暫停掃描",
            command=self.toggle_scan_pause,
            state=tk.DISABLED,
        )
        self.scan_pause_btn.pack(side=tk.LEFT, padx=5)

        # 檔案列表區域
        self.tree_frame = ttk.LabelFrame(self.window, text="檔案列表")
        self.tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tree = ttk.Treeview(
            self.tree_frame,
            selectmode="none",
            show=("tree", "headings"),
            style="Custom.Treeview",  # 使用自定義樣式
        )

        # 創建自定義樣式
        style = ttk.Style()
        style.configure(
            "Custom.Treeview",
            rowheight=25,  # 增加行高以容納更大的勾選框
        )

        # 設置列配置
        self.tree["columns"] = ("size", "type")
        self.tree.heading("#0", text="名稱", command=lambda: self.sort_tree("name"))
        self.tree.heading("size", text="大小", command=lambda: self.sort_tree("size"))
        self.tree.heading("type", text="類型", command=lambda: self.sort_tree("type"))

        # 設置列寬
        self.tree.column("#0", minwidth=300, width=400)
        self.tree.column("size", width=100)
        self.tree.column("type", width=150)

        # 綁定右鍵選單
        self.tree.bind("<Button-3>", self.show_context_menu)

        # 創建右鍵選單
        self.context_menu = tk.Menu(self.window, tearoff=0)
        self.context_menu.add_command(label="全選", command=self.select_all)
        self.context_menu.add_command(label="取消全選", command=self.deselect_all)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="展開所有", command=self.expand_all)
        self.context_menu.add_command(label="收起所有", command=self.collapse_all)

        # 排序狀態
        self.sort_column = None
        self.sort_reverse = False

        # 用於追踪勾選狀態
        self.checked_items = set()

        # 修改勾選框圖標
        self.checkbox_unchecked = "☐"  # 未選中
        self.checkbox_checked = "✅"  # 已選中
        self.folder_icon = "📁"  # 資料夾
        self.file_icon = "📄"  # 檔案

        # 用於追踪資料夾結構
        self.folders = {}

        self.scrollbar = ttk.Scrollbar(
            self.tree_frame, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=self.scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 修改綁定事件
        self.tree.bind("<Button-1>", self.on_tree_click)

        # 下載控制區域
        control_frame = ttk.Frame(self.window)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        self.download_btn = ttk.Button(
            control_frame, text="下載選擇的檔案", command=self.download_selected
        )
        self.download_btn.pack(side=tk.LEFT, padx=5)

        self.pause_btn = ttk.Button(
            control_frame, text="暫停下載", command=self.toggle_pause, state=tk.DISABLED
        )
        self.pause_btn.pack(side=tk.LEFT, padx=5)

        self.path_btn = ttk.Button(
            control_frame, text="選擇下載位置", command=self.choose_download_path
        )
        self.path_btn.pack(side=tk.LEFT, padx=5)

        # 進度條
        self.progress_frame = ttk.LabelFrame(self.window, text="進度")
        self.progress_frame.pack(fill=tk.X, padx=5, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, variable=self.progress_var, maximum=100
        )
        self.progress_bar.pack(fill=tk.X, padx=5, pady=2)

        self.progress_label = ttk.Label(self.progress_frame, text="")
        self.progress_label.pack(pady=2)

        # 添加新的初始化變數
        self.files_dict = {}
        self.download_path = ""  # 初始化為空字串
        self.is_paused = False
        self.download_queue = Queue()
        self.max_workers = 3  # 同時下載的最大檔案數
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.active_downloads = []

        # 添加下載線程數量控制
        threads_frame = ttk.Frame(control_frame)
        threads_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(threads_frame, text="同時下載數:").pack(side=tk.LEFT)
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

        # 配置 requests session
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,  # 總重試次數
            backoff_factor=1,  # 重試間隔
            status_forcelist=[500, 502, 503, 504],  # 需要重試的HTTP狀態碼
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,  # 連接池大小
            pool_maxsize=10,  # 最大連接數
            pool_block=False,  # 連接池滿時不阻塞
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # 設置更長的超時時間
        self.timeout = (10, 30)  # (連接超時, 讀取超時)

        # 添加掃描進度變數
        self.total_urls = 0
        self.scanned_urls = 0

        # 添加視窗關閉事件處理
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 添加線程控制
        self.should_stop = False

    def choose_download_path(self):
        path = filedialog.askdirectory(title="選擇下載位置")
        if path:
            self.download_path = path

    def toggle_pause(self):
        if self.is_paused:
            self.pause_event.set()
            self.pause_btn.configure(text="暫停下載")
            self.is_paused = False
        else:
            self.pause_event.clear()
            self.pause_btn.configure(text="繼續下載")
            self.is_paused = True

    def toggle_scan_pause(self):
        """切換掃描暫停狀態"""
        if self.scan_pause_event.is_set():
            self.scan_pause_event.clear()
            self.scan_pause_btn.configure(text="繼續掃描")
            self.progress_label.config(text="掃描已暫停")
        else:
            self.scan_pause_event.set()
            self.scan_pause_btn.configure(text="暫停掃描")

    def filter_file_type(self, file_name):
        """檢查檔案是否應該顯示"""
        ext = os.path.splitext(file_name)[1].lower()
        if not ext:
            ext = "(無副檔名)"
        if ext.startswith("."):
            ext = ext[1:]
        ext = f".{ext}"

        # 檢查是否存在相同的檔案類型（忽略大小寫）
        existing_ext = next(
            (e for e in self.file_types.keys() if e.lower() == ext.lower()), None
        )

        return existing_ext is not None and self.file_types[existing_ext].get()

    def create_folder_structure(self, path, url):
        """創建資料夾結構並返回最後一個資料夾的ID"""
        print("\n=== 開始創建資料夾結構 ===")
        print(f"原始路徑: {path}")
        print(f"原始URL: {url}")

        # 標準化路徑格式並進行URL解碼
        path = unquote(path.replace("\\", "/"))
        path = posixpath.normpath(path).strip("/")
        print(f"標準化後的路徑: {path}")
        print(f"現有資料夾: {list(self.folders.keys())}")

        if not path:
            return ""

        # 使用完整路徑作為唯一標識
        parts = path.split("/")
        current_path = ""
        parent = ""

        for part in parts:
            if not part:  # 跳過空的部分
                continue

            current_path = posixpath.join(current_path, part) if current_path else part
            print(f"\n處理資料夾: {part}")
            print(f"當前完整路徑: {current_path}")

            # 檢查完整路徑是否已存在
            if current_path in self.folders:
                print(f"找到現有資料夾: {current_path}")
                parent = self.folders[current_path]["id"]
                continue

            print(f"創建新資料夾: {current_path}")
            folder_id = self.tree.insert(
                parent,
                "end",
                text=f"{self.checkbox_unchecked} {self.folder_icon} {part}",
                values=("", "目錄"),
                tags=("folder", "unchecked"),
            )
            self.folders[current_path] = {
                "id": folder_id,
                "url": urljoin(url, current_path),
                "full_path": current_path,
            }
            parent = folder_id

        print("\n=== 資料夾結構創建完成 ===")
        return parent

    def _get_ancestors(self, item):
        """獲取項目的所有祖先節點"""
        ancestors = []
        parent = self.tree.parent(item)
        while parent:
            ancestors.append(parent)
            parent = self.tree.parent(parent)
        return ancestors

    def on_tree_click(self, event):
        """處理樹狀圖點擊事件"""
        print("\n=== 處理點擊事件 ===")
        item = self.tree.identify("item", event.x, event.y)
        if not item:
            return

        # 計算點擊位置
        item_x = int(self.tree.bbox(item)[0])
        relative_x = event.x - item_x
        
        # 定義區域寬度
        arrow_width = 30
        checkbox_width = 30
        
        print(f"相對點擊位置: {relative_x}")
        
        if relative_x < arrow_width:
            print("點擊箭頭區域")
            # 展開/收合資料夾的預設行為
            return
        elif relative_x < arrow_width + checkbox_width:
            print("點擊勾選框區域")
            self.toggle_check(item)
        else:
            print("點擊名稱區域")

    def toggle_check(self, item, force_check=None, force_uncheck=None):
        """切換項目的勾選狀態"""
        print("\n=== 開始切換勾選狀態 ===")
        print(f"處理項目ID: {item}")

        if not self.tree.exists(item):
            print("錯誤：項目不存在")
            return

        # 獲取當前項目資訊
        current_item = self.tree.item(item)
        text = current_item["text"]
        tags = current_item["tags"]
        print(f"當前文字: {text}")
        print(f"當前標籤: {tags}")

        parts = text.split(" ", 2)
        if len(parts) < 3:
            print(f"錯誤：文字格式不正確 - {text}")
            return

        checkbox, icon, name = parts
        print(f"分解結果：checkbox='{checkbox}', icon='{icon}', name='{name}'")

        # 決定新的勾選狀態
        print("\n檢查勾選狀態:")
        print(f"force_check: {force_check}")
        print(f"force_uncheck: {force_uncheck}")
        print(f"當前checkbox: {checkbox}")
        print(f"checkbox_unchecked: {self.checkbox_unchecked}")

        if force_check is not None:
            is_checked = force_check
            print(f"強制勾選: {is_checked}")
        elif force_uncheck is not None:
            is_checked = not force_uncheck
            print(f"強制取消勾選: {is_checked}")
        else:
            is_checked = checkbox == self.checkbox_unchecked
            print(f"切換狀態: {is_checked}")

        # 更新勾選框
        new_checkbox = self.checkbox_checked if is_checked else self.checkbox_unchecked
        new_text = f"{new_checkbox} {icon} {name}"
        print(f"\n更新項目:")
        print(f"新勾選框: {new_checkbox}")
        print(f"新文字: {new_text}")

        self.tree.item(item, text=new_text)

        # 更新勾選集合
        print("\n更新勾選集合:")
        print(f"項目 {item} 之前是否在集合中: {item in self.checked_items}")
        if is_checked:
            self.checked_items.add(item)
            print(f"已加入集合")
        else:
            self.checked_items.discard(item)
            print(f"已從集合移除")
        print(f"目前集合大小: {len(self.checked_items)}")

        # 如果是資料夾，遞迴處理子項目
        if "folder" in tags:
            for child in self.tree.get_children(item):
                self.toggle_check(child, force_check=is_checked)

        print("=== 切換勾選狀態完成 ===\n")

    def scan_website(self, url):
        try:
            self.is_scanning = True
            self.scan_pause_btn.configure(state=tk.NORMAL)
            self.progress_label.config(text="正在掃描網站...")
            self.scan_btn.configure(state=tk.DISABLED)

            # 清除現有記錄
            self.folders.clear()
            self.tree.delete(*self.tree.get_children())
            self.files_dict.clear()

            # 重置掃描進度
            self.total_urls = 0
            self.scanned_urls = 0

            # 先獲取所有URL
            all_urls = self._get_all_urls(url)
            self.total_urls = len(all_urls)

            # 使用線程池處理URL
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for url_info in all_urls:
                    if self.should_stop:  # 檢查是否應該停止
                        break

                    # 等待繼續掃描
                    self.scan_pause_event.wait()

                    if url_info["is_directory"]:
                        futures.append(
                            executor.submit(self._process_directory, url_info["url"])
                        )
                    else:
                        futures.append(
                            executor.submit(self._process_file, url_info["url"])
                        )

                # 等待所有任務完成
                for future in futures:
                    if self.should_stop:  # 檢查是否應該停止
                        break
                    try:
                        future.result()
                    except Exception as e:
                        print(f"處理URL時發生錯誤: {str(e)}")
                    finally:
                        if self.is_scanning:  # 只在掃描未取消時更新進度
                            self.scanned_urls += 1
                            self._update_scan_progress()

            if not self.should_stop:  # 只在正常完成時顯示結果
                if not self.files_dict:
                    messagebox.showinfo("提示", "未找到任何檔案")
                else:
                    messagebox.showinfo(
                        "完成", f"掃描完成，共找到 {len(self.files_dict)} 個檔案"
                    )

        except Exception as e:
            if self.is_scanning and not self.should_stop:  # 只在掃描未取消時顯示錯誤
                messagebox.showerror("錯誤", f"掃描時發生未知錯誤: {str(e)}")
        finally:
            self.is_scanning = False
            self.scan_btn.configure(state=tk.NORMAL, text="掃描")
            self.scan_pause_btn.configure(state=tk.DISABLED)
            self.scan_pause_event.set()  # 重置暫停狀態
            self.progress_label.config(text="")

    def _print_file_list(self):
        """輸出檔案列表到控制台"""
        print("\n=== 掃描結果 ===")
        print(f"共找到 {len(self.files_dict)} 個檔案")
        print("\n檔案列表:")

        def print_item(item, level=0):
            item_text = self.tree.item(item)["text"]
            values = self.tree.item(item)["values"]
            tags = self.tree.item(item)["tags"]

            # 移除勾選框和圖標，只保留名稱
            name = " ".join(item_text.split()[2:])

            # 根據層級添加縮進
            indent = "  " * level

            if "folder" in tags:
                print(f"{indent}📁 {name}/")
                # 遞迴輸出子項目
                for child in self.tree.get_children(item):
                    print_item(child, level + 1)
            else:
                size = values[0] if values else "Unknown"
                file_type = values[1] if len(values) > 1 else "Unknown"
                print(f"{indent}📄 {name} ({size}, {file_type})")

        # 從根節點開始遍歷
        for item in self.tree.get_children():
            print_item(item)

        print("\n=== 結束 ===\n")

    def _get_all_urls(self, url, scanned_urls=None, base_url=None):
        """獲取所有需要處理的URL"""
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

            # 使用集合來去重
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

                # 標準化路徑
                path = parsed.path.rstrip("/")
                if not path:
                    continue

                # 如果URL已經處理過，跳過
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

                # 如果是目錄且未掃描過，遞迴處理
                if is_directory and normalized_url not in scanned_urls:
                    urls.extend(
                        self._get_all_urls(normalized_url, scanned_urls, base_url)
                    )

            return urls

        except Exception as e:
            print(f"獲取URL列表時發生錯誤: {str(e)}")
            return []

    def _update_scan_progress(self):
        """更新掃描進度"""
        if self.total_urls > 0:
            progress = (self.scanned_urls / self.total_urls) * 100
            self.progress_var.set(progress)
            self.progress_label.config(
                text=f"掃描進度... ({self.scanned_urls}/{self.total_urls}) {progress:.1f}%"
            )
            self.window.update_idletasks()

    def _process_directory(self, url):
        """處理目錄"""
        try:
            parsed_path = urlparse(url).path
            dir_path = parsed_path.rstrip("/")
            self.create_folder_structure(dir_path, url)
        except Exception as e:
            print(f"處理目錄時發生錯誤: {str(e)}")

    def _process_file(self, url):
        """處理檔案"""
        try:
            print("\n=== 開始處理檔案 ===")
            print(f"處理URL: {url}")

            parsed = urlparse(url)
            file_name = unquote(os.path.basename(parsed.path))
            dir_path = unquote(os.path.dirname(parsed.path))

            print(f"檔案名稱: {file_name}")
            print(f"目錄路徑: {dir_path}")

            if not file_name:
                return

            # 標準化路徑
            full_path = os.path.join(dir_path, file_name).replace("\\", "/")
            if full_path.startswith("/"):
                full_path = full_path[1:]

            print(f"完整路徑: {full_path}")

            # 檢查檔案是否已存在
            if full_path in self.files_dict:
                print(f"檔案已存在: {full_path}")
                return

            try:
                head = self.session.head(url, timeout=(5, 10), allow_redirects=True)

                size = head.headers.get("content-length", "Unknown")
                if size != "Unknown":
                    size = f"{int(size) / 1024:.2f} KB"

                file_type = head.headers.get("content-type", "Unknown")

                # 先更新檔案類型列表
                self.window.after(0, lambda: self.update_file_types(file_name))

                # 在主線程中創建資料夾結構和添加檔案
                self.window.after(
                    0,
                    lambda: self._safe_create_folder_and_add_file(
                        dir_path, url, file_name, size, file_type, full_path
                    ),
                )

            except (requests.RequestException, socket.timeout):
                pass

        except Exception as e:
            print(f"處理檔案時發生錯誤: {str(e)}")

    def _safe_create_folder_and_add_file(
        self, dir_path, url, file_name, size, file_type, full_path
    ):
        """在主線程中安全地創建資料夾和添加檔案"""
        try:
            parent_id = self.create_folder_structure(dir_path, url)
            self._add_file_to_tree(
                parent_id, file_name, size, file_type, full_path, url
            )
        except Exception as e:
            print(f"添加檔案到樹狀結構時發生錯誤: {str(e)}")

    def _add_file_to_tree(self, parent_id, file_name, size, file_type, full_path, url):
        """在主線程中添加檔案到樹狀結構"""
        try:
            # 檢查檔案是否已存在
            for child in self.tree.get_children(parent_id):
                if self.tree.item(child)["text"].endswith(f" {file_name}"):
                    return

            # 添加檔案
            item_id = self.tree.insert(
                parent_id,
                "end",
                text=f"{self.checkbox_unchecked} {self.file_icon} {file_name}",
                values=(size, file_type),
                tags=("file", "unchecked"),
            )
            self.files_dict[full_path] = url

            # 將檔案項目添加到對應的檔案類型集合中
            ext = os.path.splitext(file_name)[1].lower()
            if not ext:
                ext = "(無副檔名)"
            if ext.startswith("."):
                ext = ext[1:]
            ext = f".{ext}"

            if hasattr(self, "_type_files"):
                if ext not in self._type_files:
                    self._type_files[ext] = set()
                self._type_files[ext].add(item_id)

            # 確保父資料夾是展開的
            current = parent_id
            while current:
                self.tree.item(current, open=True)
                current = self.tree.parent(current)

        except Exception as e:
            print(f"添加檔案到樹狀結構時發生錯誤: {str(e)}")

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
            error_msg = "網路錯誤"
            if isinstance(e, requests.exceptions.ConnectTimeout):
                error_msg = "連接超時"
            elif isinstance(e, requests.exceptions.ConnectionError):
                error_msg = "連接失敗"
            elif isinstance(e, requests.exceptions.ReadTimeout):
                error_msg = "讀取超時"

            messagebox.showerror(
                "錯誤", f"下載 {file_name} 時發生{error_msg}: {str(e)}"
            )
            return False

    def update_progress(self, file_name, progress):
        self.window.after(0, lambda: self._update_progress(file_name, progress))

    def _update_progress(self, file_name, progress):
        self.progress_var.set(progress)
        self.progress_label.config(text=f"正在下載: {file_name} ({progress:.1f}%)")

    def download_selected(self):
        """下載已勾選的檔案"""
        if not self.checked_items:
            messagebox.showwarning("警告", "請選擇要下載的檔案")
            return

        # 過濾掉資料夾，只下載檔案
        files_to_download = [
            item
            for item in self.checked_items
            if "file" in self.tree.item(item)["tags"]
        ]

        if not files_to_download:
            messagebox.showwarning("警告", "請選擇要下載的檔案")
            return

        # 如果沒有選擇下載路徑，使用預設路徑
        if not self.download_path:
            self.download_path = os.path.join(os.getcwd(), "downloads")

        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)

        self.pause_event.set()
        self.pause_btn.configure(state=tk.NORMAL)

        # 切換到下載進度顯示
        self.progress_frame.configure(text="下載進度")
        self.progress_var.set(0)
        self.progress_label.config(text="準備下載...")

        # 創建下載任務
        futures = []
        for item in files_to_download:
            # 獲取完整的檔案路徑
            file_name = " ".join(
                self.tree.item(item)["text"].split()[2:]
            )  # 移除勾選框和圖標

            # 構建檔案的完整路徑
            parent = item
            path_parts = []
            while parent:
                parent_text = self.tree.item(parent)["text"]
                if parent != item:  # 不包含檔案名
                    folder_name = " ".join(parent_text.split()[2:])  # 移除勾選框和圖標
                    path_parts.append(folder_name)
                parent = self.tree.parent(parent)

            # 反轉路徑部分並組合
            path_parts.reverse()
            relative_path = os.path.join(*path_parts) if path_parts else ""

            # 創建目標目錄
            target_dir = os.path.join(self.download_path, relative_path)
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)

            # 獲取下載URL
            full_path = os.path.join(relative_path, file_name).replace("\\", "/")
            url = self.files_dict.get(full_path)

            if url:
                file_path = os.path.join(target_dir, file_name)
                future = self.executor.submit(
                    self.download_file, url, file_path, file_name
                )
                futures.append(future)

        # 監控下載進度的線程
        def monitor_downloads():
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    print(f"下載出錯: {str(e)}")

            self.window.after(0, lambda: self._downloads_completed())

        threading.Thread(target=monitor_downloads).start()

    def _downloads_completed(self):
        self.progress_label.config(text="下載完成")
        self.pause_btn.configure(state=tk.DISABLED)
        messagebox.showinfo("完成", "選擇的檔案已下載完成")

    def start_scan(self):
        url = self.url_entry.get()
        if not url:
            messagebox.showerror("錯誤", "請輸入網址")
            return

        # 設置下載路徑為網站名稱
        try:
            parsed_url = urlparse(url)
            site_name = parsed_url.netloc.split(":")[0]  # 移除可能的端口號
            self.download_path = os.path.join(os.getcwd(), site_name)
        except Exception as e:
            print(f"設置下載路徑時發生錯誤: {str(e)}")
            self.download_path = os.path.join(os.getcwd(), "downloads")

        # 如果正在掃描，則取消掃描
        if self.is_scanning:
            self.is_scanning = False
            self.scan_btn.configure(text="掃描")
            return

        # 重置進度條和文字
        self.progress_frame.configure(text="掃描進度")
        self.progress_var.set(0)
        self.progress_label.config(text="準備掃描...")

        self.scan_btn.configure(text="停止掃描")
        Thread(target=self.scan_website, args=(url,)).start()

    def run(self):
        self.window.mainloop()

    def show_context_menu(self, event):
        """顯示右鍵選單"""
        self.context_menu.post(event.x_root, event.y_root)

    def select_all(self):
        """全選所有項目"""

        def check_all(parent=""):
            for item in self.tree.get_children(parent):
                self.toggle_check(item, force_check=True)
                if self.tree.get_children(item):  # 如果有子項目
                    check_all(item)

        check_all()

    def deselect_all(self):
        """取消全選"""

        def uncheck_all(parent=""):
            for item in self.tree.get_children(parent):
                self.toggle_check(item, force_uncheck=True)
                if self.tree.get_children(item):
                    uncheck_all(item)

        uncheck_all()

    def expand_all(self):
        """展開所有資料夾"""

        def expand(parent=""):
            for item in self.tree.get_children(parent):
                if "folder" in self.tree.item(item)["tags"]:
                    # 保持原有的標籤和勾選狀態
                    current_tags = self.tree.item(item)["tags"]
                    self.tree.item(item, open=True, tags=current_tags)
                expand(item)

        expand()

    def collapse_all(self):
        """收起所有資料夾"""

        def collapse(parent=""):
            for item in self.tree.get_children(parent):
                if "folder" in self.tree.item(item)["tags"]:
                    # 保持原有的標籤和勾選狀態
                    current_tags = self.tree.item(item)["tags"]
                    self.tree.item(item, open=False, tags=current_tags)
                collapse(item)

        collapse()

    def sort_tree(self, column):
        """排序樹狀結構"""
        # 如果點擊相同列，切換排序順序
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

        # 分別排序資料夾和檔案
        def sort_level(parent=""):
            items = self.tree.get_children(parent)
            # 分離資料夾和檔案
            folders = [
                item for item in items if "folder" in self.tree.item(item)["tags"]
            ]
            files = [item for item in items if "file" in self.tree.item(item)["tags"]]

            # 排序資料夾和檔案
            sorted_folders = sorted(
                folders, key=get_sort_key, reverse=self.sort_reverse
            )
            sorted_files = sorted(files, key=get_sort_key, reverse=self.sort_reverse)

            # 重新排列項目
            for idx, item in enumerate(sorted_folders + sorted_files):
                self.tree.move(item, parent, idx)
                # 遞迴排序子項目
                if self.tree.get_children(item):
                    sort_level(item)

        sort_level()

    def on_closing(self):
        """處理視窗關閉事件"""
        self.should_stop = True
        self.is_scanning = False

        # 等待所有線程完成
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=False)

        self.window.destroy()
        os._exit(0)  # 強制結束所有線程

    def update_file_types(self, file_name):
        """更新檔案類型列表"""
        ext = os.path.splitext(file_name)[1].lower()
        if not ext:
            ext = "(無副檔名)"

        # 標準化檔案類型
        if ext.startswith("."):
            ext = ext[1:]  # 移除開頭的點
        ext = f".{ext}"  # 統一添加點

        # 檢查是否已存在相同的檔案類型（忽略大小寫）
        existing_ext = next(
            (e for e in self.file_types.keys() if e.lower() == ext.lower()), None
        )

        if existing_ext:
            ext = existing_ext  # 使用已存在的大小寫形式
            self.file_type_counts[ext] += 1
            # 更新勾選框文字
            self.window.after(0, lambda: self._update_type_label(ext))
        else:
            # 創建新的檔案類型
            self.file_types[ext] = tk.BooleanVar(value=False)
            self.file_type_counts[ext] = 1
            if not hasattr(self, "_type_files"):
                self._type_files = {}
            self._type_files[ext] = set()
            # 在UI中添加新的勾選框
            self.window.after(0, lambda: self._add_type_checkbox(ext))

    def _add_type_checkbox(self, ext):
        """添加檔案類型勾選框"""
        frame = ttk.Frame(self.filter_checkboxes_frame)
        frame.pack(side=tk.LEFT, padx=2)

        # 創建勾選框，並綁定選擇事件
        cb = ttk.Checkbutton(
            frame,
            text=f"{ext} ({self.file_type_counts[ext]})",
            variable=self.file_types[ext],
            command=lambda: self._on_type_selected(ext),
        )
        cb.pack(side=tk.LEFT)

        # 保存勾選框引用以便更新
        if not hasattr(self, "_type_checkboxes"):
            self._type_checkboxes = {}
        self._type_checkboxes[ext] = cb

    def _on_type_selected(self, ext):
        """處理檔案類型選擇事件"""
        is_selected = self.file_types[ext].get()

        # 更新所有相關檔案的選擇狀態
        if hasattr(self, "_type_files") and ext in self._type_files:
            for item in self._type_files[ext]:
                if self.tree.exists(item):
                    if is_selected:
                        self.toggle_check(item, force_check=True)
                        # 展開到該檔案的路徑
                        self._expand_to_item(item)
                    else:
                        self.toggle_check(item, force_uncheck=True)

        # 更新檔案可見性
        self.refresh_file_list()

    def _update_type_label(self, ext):
        """更新檔案類型勾選框的文字"""
        if hasattr(self, "_type_checkboxes") and ext in self._type_checkboxes:
            self._type_checkboxes[ext].configure(
                text=f"{ext} ({self.file_type_counts[ext]})"
            )

    def select_all_types(self):
        """全選所有檔案類型"""
        # 設置所有檔案類型為選中
        for ext, var in self.file_types.items():
            var.set(True)
            # 選中該類型的所有檔案
            if hasattr(self, "_type_files") and ext in self._type_files:
                for item in self._type_files[ext]:
                    if self.tree.exists(item):
                        self.toggle_check(item, force_check=True)

        # 更新檔案可見性
        self.refresh_file_list()

    def deselect_all_types(self):
        """取消全選所有檔案類型"""
        # 設置所有檔案類型為未選中
        for ext, var in self.file_types.items():
            var.set(False)
            # 取消選中該類型的所有檔案
            if hasattr(self, "_type_files") and ext in self._type_files:
                for item in self._type_files[ext]:
                    if self.tree.exists(item):
                        self.toggle_check(item, force_uncheck=True)

        # 更新檔案可見性
        self.refresh_file_list()

    def refresh_file_list(self):
        """根據選擇的檔案類型重新過濾檔案列表"""
        for item in self.tree.get_children():
            self._refresh_item_visibility(item)

    def _refresh_item_visibility(self, item):
        """遞迴更新項目的可見性"""
        is_folder = "folder" in self.tree.item(item)["tags"]

        if is_folder:
            # 遞迴處理子項目
            has_visible_children = False
            for child in self.tree.get_children(item):
                if self._refresh_item_visibility(child):
                    has_visible_children = True

            # 如果資料夾有可見的子項目，則顯示資料夾
            if has_visible_children:
                self.tree.item(item, tags=("folder", "unchecked"))
                return True
            else:
                self.tree.item(item, tags=("folder", "unchecked", "hidden"))
                return False
        else:
            # 檢查檔案類型是否被選中
            file_name = " ".join(self.tree.item(item)["text"].split()[2:])
            ext = os.path.splitext(file_name)[1].lower()
            if not ext:
                ext = "(無副檔名)"

            if ext in self.file_types and self.file_types[ext].get():
                self.tree.item(item, tags=("file", "unchecked"))
                return True
            else:
                self.tree.item(item, tags=("file", "unchecked", "hidden"))
                return False

    def _expand_to_item(self, item):
        """展開到指定項目的路徑"""
        parent = self.tree.parent(item)
        while parent:
            self.tree.item(parent, open=True)
            parent = self.tree.parent(parent)

    def setup_tree(self):
        """設置檔案樹狀圖"""
        print("\n=== 初始化樹狀圖 ===")
        
        # 建立樹狀圖框架
        self.tree_frame = ttk.Frame(self.window)
        self.tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 自定義樹狀圖樣式
        style = ttk.Style()
        style.configure("Custom.Treeview", 
                       indent=30,
                       background="#ffffff",
                       fieldbackground="#ffffff")

        # 建立樹狀圖和捲動條
        self.tree = ttk.Treeview(
            self.tree_frame, 
            columns=("size", "type"), 
            selectmode="none",
            style="Custom.Treeview"
        )
        
        # 設置不同區域的標籤和樣式
        self.tree.tag_configure('arrow_zone', background='#f0f0f0')  # 箭頭區域
        self.tree.tag_configure('checkbox_zone', background='#e8e8e8')  # 勾選框區域
        self.tree.tag_configure('name_zone', background='#ffffff')  # 名稱區域
        
        # 綁定滑鼠移動事件來顯示區域
        self.tree.bind('<Motion>', self.on_mouse_move)
        self.tree.bind("<Button-1>", self.on_tree_click)
        
        # 設置列標題
        self.tree.heading("#0", text="名稱")
        self.tree.heading("size", text="大小")
        self.tree.heading("type", text="類型")

        # 設置列寬度
        self.tree.column("#0", width=400, minwidth=200)
        self.tree.column("size", width=100)
        self.tree.column("type", width=100)

        print("樹狀圖設置完成")

    def on_mouse_move(self, event):
        """處理滑鼠移動事件"""
        item = self.tree.identify("item", event.x, event.y)
        if not item:
            return

        # 清除所有項目的背景色
        for tag in ['arrow_zone', 'checkbox_zone', 'name_zone']:
            self.tree.tag_remove(tag, item)

        # 根據滑鼠位置設置背景色
        region = self.tree.identify("region", event.x, event.y)
        if region == "tree":
            # 計算不同區域的x座標範圍
            item_x = int(self.tree.bbox(item)[0])  # 項目起始x座標
            arrow_width = 30  # 箭頭區域寬度
            checkbox_width = 30  # 勾選框區域寬度
            
            if event.x < item_x + arrow_width:
                self.tree.tag_add('arrow_zone', item)
            elif event.x < item_x + arrow_width + checkbox_width:
                self.tree.tag_add('checkbox_zone', item)
            else:
                self.tree.tag_add('name_zone', item)


if __name__ == "__main__":
    app = WebsiteCopier()
    app.run()
