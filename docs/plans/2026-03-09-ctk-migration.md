# CustomTkinter 遷移實作計劃

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 建立 `ui_ctk.py`，以 CustomTkinter 統一 UI 框架，取代 ttkbootstrap 版本，保留所有現有功能。

**Architecture:** 保留 `ui_ttkb.py` 的模組化架構（Queue + after() 執行緒安全模式），以 CTk widget 替換 ttkbootstrap widget。`ui_downloads.py` 幾乎不動（已是 CTk）。`ttk.Treeview` 保留（CTk 無此 widget），以 `ttk.Style()` 配合 CTk 主題色。

**Tech Stack:** customtkinter>=5.2.0、tkinter（內建）、ttk.Treeview（內建）、requests、backend.py（不動）

**References:**
- `ui_ttkb.py`：架構參考（模組化、Queue 模式）
- `index_ripper.py`：CTk widget 用法參考（舊版但已是 CTk）
- `ui_downloads.py`：DownloadsPanel（直接沿用）
- `ui_theme.py`：design token（清理後沿用）
- `docs/plans/2026-03-09-ctk-migration-design.md`：設計文件

---

### Task 1: 清理 ui_theme.py

**目的：** 移除 ttkbootstrap bridge，只保留 CTk 相關的 token 與 Treeview style。

**Files:**
- Modify: `ui_theme.py`

**Step 1: 確認現有內容**

讀 `ui_theme.py` 全文，確認要刪的函式：
- `apply_bootstrap_theme()` — 刪除（ttkb 專用）
- 其餘全部保留

**Step 2: 刪除 apply_bootstrap_theme**

從 `ui_theme.py` 移除 `apply_bootstrap_theme` 函式（第 10–22 行）。

修改後確保剩下：
- `apply_app_theme(ctk)` ✓
- `ui_tokens()` ✓
- `action_button_style_name(kind)` ✓
- `configure_action_button_styles(window, ctk, ttk)` ✓
- `configure_treeview_style(window, ctk, ttk)` ✓
- `treeview_tag_colors(window)` ✓

**Step 3: 確認 index_ripper.py 的 import 仍正常**

`index_ripper.py` 第 66–73 行 import 了 `apply_bootstrap_theme`，也要同步移除該行。

**Step 4: 執行現有測試確認不壞**

```bash
python -m pytest test_ui_theme.py -v
```

Expected: 所有 PASS（若有失敗，修正後再繼續）

**Step 5: Commit**

```bash
git add ui_theme.py index_ripper.py
git commit -m "refactor(theme): 移除 ttkbootstrap bridge，統一用 CTk token"
```

---

### Task 2: ui_ctk.py 骨架 + 視窗建立

**目的：** 建立 `ui_ctk.py`，包含 `WebsiteCopierCtk` 類別的骨架、視窗初始化、以及 smoke 模式支援。

**Files:**
- Create: `ui_ctk.py`
- Create: `test_ui_ctk.py`

**Step 1: 先寫失敗測試**

建立 `test_ui_ctk.py`：

```python
"""Smoke tests for ui_ctk.WebsiteCopierCtk."""
import os
import sys
import unittest

os.environ.setdefault("INDEX_RIPPER_MODAL_DIALOGS", "0")


class TestWebsiteCopierCtkSmoke(unittest.TestCase):
    def _make(self):
        import importlib
        mod = importlib.import_module("ui_ctk")
        return mod.WebsiteCopierCtk(ui_smoke=True)

    def test_import(self):
        import ui_ctk  # noqa: F401

    def test_smoke_init_and_destroy(self):
        app = self._make()
        app.window.after(0, app.window.destroy)
        app.run()

    def test_has_url_var(self):
        app = self._make()
        app.window.after(0, app.window.destroy)
        app.run()
        self.assertTrue(hasattr(app, "url_var"))

    def test_has_log_text(self):
        app = self._make()
        app.window.after(0, app.window.destroy)
        app.run()
        self.assertTrue(hasattr(app, "log_text"))


if __name__ == "__main__":
    unittest.main()
```

**Step 2: 執行確認失敗**

```bash
python -m pytest test_ui_ctk.py -v
```

Expected: `ModuleNotFoundError: No module named 'ui_ctk'`

**Step 3: 建立 ui_ctk.py 骨架**

```python
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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
        self.file_type_widgets: dict[str, ctk.CTkCheckBox] = {}

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

    def _build_ui(self) -> None:
        if self._ui_smoke:
            self._build_ui_smoke_only()
            return
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
        # 後續 Task 中逐步實作
        pass

    def run(self) -> None:
        self.window.mainloop()

    def on_closing(self) -> None:
        self.executor.shutdown(wait=False)
        self.window.destroy()

    def log_message(self, message: str) -> None:
        try:
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
        except Exception:
            pass

    def _debug(self, message: str) -> None:
        if not self.debug_enabled:
            return
        try:
            print(f"[DEBUG] {message}")
        except Exception:
            pass
        try:
            if hasattr(self, "log_text"):
                self.log_text.insert("end", f"[DEBUG] {message}\n")
                self.log_text.see("end")
        except Exception:
            pass

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
```

**Step 4: 執行測試確認通過**

```bash
python -m pytest test_ui_ctk.py -v
```

Expected: 4 PASS

**Step 5: Commit**

```bash
git add ui_ctk.py test_ui_ctk.py
git commit -m "feat(ui): 新增 WebsiteCopierCtk 骨架與 smoke 測試"
```

---

### Task 3: Header 列（URL 輸入 + Status + 掃描按鈕）

**目的：** 實作視窗頂部的 URL 輸入框、狀態標籤、Scan / Pause Scan / Clear 按鈕。

**Files:**
- Modify: `ui_ctk.py`（`_build_full_ui` 內容）
- Modify: `test_ui_ctk.py`

**Step 1: 新增失敗測試**

在 `test_ui_ctk.py` 加入：

```python
def test_full_ui_has_scan_btn(self):
    import ui_ctk
    app = ui_ctk.WebsiteCopierCtk(ui_smoke=False)
    app.window.after(0, app.window.destroy)
    app.run()
    self.assertTrue(hasattr(app, "scan_btn"))
    self.assertTrue(hasattr(app, "url_entry"))
    self.assertTrue(hasattr(app, "status_label"))
```

**Step 2: 執行確認失敗**

```bash
python -m pytest test_ui_ctk.py::TestWebsiteCopierCtkSmoke::test_full_ui_has_scan_btn -v
```

Expected: FAIL（`AttributeError: scan_btn`）

**Step 3: 實作 _build_full_ui header 部分**

在 `ui_ctk.py` 的 `_build_full_ui` 中加入：

```python
def _build_full_ui(self) -> None:
    self.window.grid_columnconfigure(0, weight=1)
    self.window.grid_rowconfigure(2, weight=1)

    # --- Header ---
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
        command=self.toggle_scan_pause,
        state="disabled",
    )
    self.scan_pause_btn.pack(side="left", padx=3)

    self.clear_scan_btn = ctk.CTkButton(
        actions, text="Clear",
        fg_color=("gray70", "gray30"),
        command=self.clear_scan_results,
    )
    self.clear_scan_btn.pack(side="left", padx=3)

    # URL paste bindings
    self.url_context_menu = tk.Menu(self.window, tearoff=0)
    self.url_context_menu.add_command(label="Paste", command=self._paste_into_url_entry)
    self.url_entry.bind("<Command-v>", self._on_url_paste)
    self.url_entry.bind("<Command-V>", self._on_url_paste)
    self.url_entry.bind("<Control-v>", self._on_url_paste)
    self.url_entry.bind("<Control-V>", self._on_url_paste)
    self.url_entry.bind("<Shift-Insert>", self._on_url_paste)
    self.url_entry.bind("<Button-2>", self._show_url_context_menu)
    self.url_entry.bind("<Button-3>", self._show_url_context_menu)

    # 繼續後面的 Task
    self._build_filters_row()
    self._build_treeview()
    self._build_progress_section()
    self._build_panels()
    self._build_download_controls()

    # 初始化其他狀態
    self.sort_reverse = False
    self.full_tree_backup = {}
    self.drag_anchor_item = ""

    context_menu = tk.Menu(self.window, tearoff=0)
    context_menu.add_command(label="Select All", command=self.select_all)
    context_menu.add_command(label="Deselect All", command=self.deselect_all)
    context_menu.add_separator()
    context_menu.add_command(label="Expand All", command=self.expand_all)
    context_menu.add_command(label="Collapse All", command=self.collapse_all)
    self.context_menu = context_menu
```

並新增 URL paste 輔助方法（從 `ui_ttkb.py` 直接搬）：

```python
def _on_url_paste(self, _event=None):
    self._paste_into_url_entry()
    return "break"

def _on_global_url_paste(self, _event=None):
    try:
        focused = self.window.focus_get()
    except tk.TclError:
        return None
    if focused is self.url_entry._entry:  # CTkEntry 內部 widget
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
```

**Step 4: 執行測試**

```bash
python -m pytest test_ui_ctk.py -v
```

Expected: 5 PASS（新的失敗的測試現在應通過）

> 注意：`_build_filters_row` 等還未存在，需先加入空的 stub：
```python
def _build_filters_row(self): pass
def _build_treeview(self): pass
def _build_progress_section(self): pass
def _build_panels(self): pass
def _build_download_controls(self): pass
```

**Step 5: Commit**

```bash
git add ui_ctk.py test_ui_ctk.py
git commit -m "feat(ui): 實作 header 列（URL、狀態、掃描按鈕）"
```

---

### Task 4: 篩選列（檔案類型 Checkboxes）

**目的：** 動態產生 CTkCheckBox（依副檔名），支援水平捲動，Select All / Deselect All。

**Files:**
- Modify: `ui_ctk.py`（`_build_filters_row` + 相關方法）
- Modify: `test_ui_ctk.py`

**Step 1: 新增失敗測試**

```python
def test_has_filters_frame(self):
    import ui_ctk
    app = ui_ctk.WebsiteCopierCtk(ui_smoke=False)
    app.window.after(0, app.window.destroy)
    app.run()
    self.assertTrue(hasattr(app, "filters_container"))
```

**Step 2: 執行確認失敗**

```bash
python -m pytest test_ui_ctk.py::TestWebsiteCopierCtkSmoke::test_has_filters_frame -v
```

**Step 3: 實作 _build_filters_row**

```python
def _build_filters_row(self) -> None:
    filters_and_controls = ctk.CTkFrame(self.window, fg_color="transparent")
    filters_and_controls.grid(row=1, column=0, sticky="ew", padx=10, pady=(4, 0))
    filters_and_controls.grid_columnconfigure(0, weight=1)

    filters_frame = ctk.CTkFrame(filters_and_controls, fg_color="transparent")
    filters_frame.grid(row=0, column=0, sticky="ew")

    # 可水平捲動的容器
    self.filters_container = ctk.CTkScrollableFrame(
        filters_frame, height=85, orientation="horizontal", fg_color="transparent"
    )
    self.filters_container.pack(fill="x")

    type_actions = ctk.CTkFrame(filters_frame, fg_color="transparent")
    type_actions.pack(fill="x", pady=(4, 0))
    ctk.CTkButton(
        type_actions, text="Select All Types",
        fg_color=("gray80", "gray25"),
        text_color=("gray10", "gray90"),
        command=self.select_all_types,
        width=140,
    ).pack(side="left", padx=(0, 6))
    ctk.CTkButton(
        type_actions, text="Deselect All Types",
        fg_color=("gray80", "gray25"),
        text_color=("gray10", "gray90"),
        command=self.deselect_all_types,
        width=150,
    ).pack(side="left")
```

並新增 filter 方法 stub（從 `ui_ttkb.py` 搬）：

```python
def select_all_types(self):
    for var in self.file_types.values():
        var.set(True)

def deselect_all_types(self):
    for var in self.file_types.values():
        var.set(False)

def _add_file_type_filter(self, ext: str) -> None:
    if ext in self.file_types:
        return
    var = tk.BooleanVar(value=True)
    self.file_types[ext] = var
    self.file_type_counts[ext] = 0
    cb = ctk.CTkCheckBox(
        self.filters_container,
        text=ext or "(no ext)",
        variable=var,
        onvalue=True,
        offvalue=False,
    )
    cb.pack(side="left", padx=4)
    self.file_type_widgets[ext] = cb
```

**Step 4: 執行測試**

```bash
python -m pytest test_ui_ctk.py -v
```

Expected: 全部 PASS

**Step 5: Commit**

```bash
git add ui_ctk.py test_ui_ctk.py
git commit -m "feat(ui): 實作檔案類型篩選列（CTkCheckBox + 捲動容器）"
```

---

### Task 5: 下載控制列

**目的：** Download Selected、Pause/Resume、Choose Folder、Threads 選單、Hide/Show Panels。

**Files:**
- Modify: `ui_ctk.py`（`_build_download_controls`）

**Step 1: 新增失敗測試**

```python
def test_has_download_controls(self):
    import ui_ctk
    app = ui_ctk.WebsiteCopierCtk(ui_smoke=False)
    app.window.after(0, app.window.destroy)
    app.run()
    self.assertTrue(hasattr(app, "download_btn"))
    self.assertTrue(hasattr(app, "pause_btn"))
    self.assertTrue(hasattr(app, "threads_var"))
```

**Step 2: 實作 _build_download_controls**

```python
def _build_download_controls(self) -> None:
    controls_frame = ctk.CTkFrame(self.window, fg_color="transparent")
    # 放在 filters_and_controls 右側（與 Task 4 的 grid 同 row）
    # 重新取得 filters_and_controls 參考，或在 Task 4 儲存 self._filters_and_controls
    # 建議：在 Task 4 儲存 self._filters_ctrl_frame = filters_and_controls
    controls_frame.grid(row=1, column=0, sticky="e", padx=10)

    self.download_btn = ctk.CTkButton(
        controls_frame, text="Download Selected", command=self.download_selected
    )
    self.download_btn.grid(row=0, column=0, padx=4)

    self.pause_btn = ctk.CTkButton(
        controls_frame, text="Pause",
        fg_color=("gray70", "gray30"),
        command=self.toggle_pause,
        state="disabled",
    )
    self.pause_btn.grid(row=0, column=1, padx=4)

    self.path_btn = ctk.CTkButton(
        controls_frame, text="Choose Folder",
        fg_color=("gray70", "gray30"),
        command=self.choose_download_path,
    )
    self.path_btn.grid(row=0, column=2, padx=4)

    ctk.CTkLabel(controls_frame, text="Threads").grid(row=0, column=3, padx=(12, 4))
    self.threads_var = tk.StringVar(value="5")
    self.threads_combo = ctk.CTkOptionMenu(
        controls_frame,
        values=[str(i) for i in range(1, 11)],
        variable=self.threads_var,
        command=self.update_thread_count,
        width=70,
    )
    self.threads_combo.grid(row=0, column=4)

    self.panels_visible = True
    self.toggle_panels_btn = ctk.CTkButton(
        controls_frame, text="Hide Panels",
        fg_color=("gray80", "gray25"),
        text_color=("gray10", "gray90"),
        command=self.toggle_panels,
        width=110,
    )
    self.toggle_panels_btn.grid(row=0, column=5, padx=(10, 0))
```

> **重要：** `_build_download_controls` 需要嵌入 `filters_and_controls` 這個 frame（同一個 grid row）。
> 建議在 Task 4 修改，讓 `_build_filters_row` 存 `self._ctrl_row_frame = filters_and_controls`，
> 然後在 `_build_download_controls` 直接用 `self._ctrl_row_frame`。

新增 stub 方法：

```python
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
```

**Step 3: 執行測試**

```bash
python -m pytest test_ui_ctk.py -v
```

**Step 4: Commit**

```bash
git add ui_ctk.py test_ui_ctk.py
git commit -m "feat(ui): 實作下載控制列"
```

---

### Task 6: Treeview（掃描結果列表）

**目的：** 建立 `ttk.Treeview`，含搜尋欄、欄位排序、行勾選、鍵盤與滑鼠互動、右鍵選單。

**Files:**
- Modify: `ui_ctk.py`（`_build_treeview` + 互動方法）
- Modify: `test_ui_ctk.py`

**Step 1: 新增失敗測試**

```python
def test_has_treeview(self):
    import ui_ctk
    app = ui_ctk.WebsiteCopierCtk(ui_smoke=False)
    app.window.after(0, app.window.destroy)
    app.run()
    self.assertTrue(hasattr(app, "tree"))
    self.assertTrue(hasattr(app, "search_var"))
```

**Step 2: 實作 _build_treeview**

```python
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
```

**Step 3: 搬移 Treeview 互動方法（從 ui_ttkb.py）**

以下方法直接從 `ui_ttkb.py` 搬移，邏輯不變：

- `on_tree_click(event)` — 點擊切換 ✔ 勾選
- `on_tree_drag_select(event)` — 拖曳多選
- `on_tree_space(event)` — Space 切換勾選
- `on_tree_enter(event)` — Enter 確認
- `_on_tree_select_all(event)` — Cmd/Ctrl+A
- `show_context_menu(event)` — 右鍵選單
- `select_all()` / `deselect_all()` — 全選/取消全選
- `expand_all()` / `collapse_all()` — 展開/收合
- `sort_tree(col)` — 欄位排序

在 `ui_ttkb.py` 中找到這些方法並直接複製（它們純粹操作 ttk.Treeview，與框架無關）。

**Step 4: 執行測試**

```bash
python -m pytest test_ui_ctk.py -v
```

**Step 5: Commit**

```bash
git add ui_ctk.py test_ui_ctk.py
git commit -m "feat(ui): 實作 Treeview 與互動邏輯"
```

---

### Task 7: 進度條區塊

**目的：** 整體下載進度條 + 進度文字。

**Files:**
- Modify: `ui_ctk.py`（`_build_progress_section`）

**Step 1: 新增失敗測試**

```python
def test_has_progress_bar(self):
    import ui_ctk
    app = ui_ctk.WebsiteCopierCtk(ui_smoke=False)
    app.window.after(0, app.window.destroy)
    app.run()
    self.assertTrue(hasattr(app, "progress_bar"))
    self.assertTrue(hasattr(app, "progress_label"))
```

**Step 2: 實作**

```python
def _build_progress_section(self) -> None:
    progress_frame = ctk.CTkFrame(self.window, fg_color="transparent")
    progress_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(4, 0))
    progress_frame.grid_columnconfigure(0, weight=1)

    self.progress_var = tk.DoubleVar(value=0)
    self.progress_bar = ctk.CTkProgressBar(progress_frame)
    self.progress_bar.set(0)
    self.progress_bar.grid(row=0, column=0, sticky="ew")

    self.progress_label = ctk.CTkLabel(progress_frame, text="")
    self.progress_label.grid(row=1, column=0, sticky="w")
```

**Step 3: 執行測試**

```bash
python -m pytest test_ui_ctk.py -v
```

**Step 4: Commit**

```bash
git add ui_ctk.py test_ui_ctk.py
git commit -m "feat(ui): 實作進度條區塊"
```

---

### Task 8: Tabs 面板（Downloads + Logs）

**目的：** `ctk.CTkTabview` 包含 Downloads tab（DownloadsPanel）和 Logs tab（CTkTextbox）。

**Files:**
- Modify: `ui_ctk.py`（`_build_panels`）
- Modify: `test_ui_ctk.py`

**Step 1: 新增失敗測試**

```python
def test_has_panels_notebook(self):
    import ui_ctk
    app = ui_ctk.WebsiteCopierCtk(ui_smoke=False)
    app.window.after(0, app.window.destroy)
    app.run()
    self.assertTrue(hasattr(app, "panels_notebook"))
    self.assertTrue(hasattr(app, "log_text"))
    self.assertTrue(hasattr(app, "downloads_panel"))
```

**Step 2: 實作 _build_panels**

```python
def _build_panels(self) -> None:
    self.panels_notebook = ctk.CTkTabview(self.window, height=180)
    self.panels_notebook.grid(row=4, column=0, sticky="ew", padx=10, pady=(4, 10))
    self._panels_widget = self.panels_notebook  # toggle_panels 用

    downloads_tab = self.panels_notebook.add("Downloads")
    logs_tab = self.panels_notebook.add("Logs")
    self.panels_notebook.set("Logs")  # 預設顯示 Logs

    # Downloads tab
    downloads_scroll = ctk.CTkScrollableFrame(downloads_tab, height=120)
    downloads_scroll.pack(fill="both", expand=True)
    self.downloads_panel = DownloadsPanel(
        parent_frame=downloads_scroll,
        ctk=ctk,
        tk=tk,
        tokens=self.ui_tokens,
    )

    # Logs tab
    self.log_text = ctk.CTkTextbox(logs_tab, height=120, wrap="word")
    self.log_text.pack(fill="both", expand=True)
```

**Step 3: 更新 log_message 方法**

`ctk.CTkTextbox` 的 API 與 `tk.Text` 略不同：

```python
def log_message(self, message: str) -> None:
    try:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
    except Exception:
        pass
```

**Step 4: 執行測試**

```bash
python -m pytest test_ui_ctk.py -v
```

**Step 5: Commit**

```bash
git add ui_ctk.py test_ui_ctk.py
git commit -m "feat(ui): 實作 CTkTabview（Downloads + Logs）"
```

---

### Task 9: Queue 輪詢 + 執行緒安全

**目的：** 確保 `after()` 輪詢 Queue 的機制完整移植，包含 scan buffer throttle。

**Files:**
- Modify: `ui_ctk.py`

**Step 1: 從 ui_ttkb.py 搬移以下方法（邏輯不變）**

在 `WebsiteCopierCtk.__init__` 末尾啟動輪詢：

```python
# 在 _build_ui() 之後加入
if not self._ui_smoke:
    self.window.after(100, self._poll_scan_queue)
    self.window.after(100, self._poll_file_queue)
```

從 `ui_ttkb.py` 直接搬移以下方法：
- `_poll_scan_queue()`
- `_poll_file_queue()`
- `_flush_scan_buffer()`
- `_schedule_flush()`

這些方法只用到 `self.scan_item_buffer`、`self.dir_queue`、`self.file_queue` 與 Treeview 操作，與框架無關，可直接複製。

**Step 2: 新增測試**

```python
def test_poll_methods_exist(self):
    import ui_ctk
    app = ui_ctk.WebsiteCopierCtk(ui_smoke=True)
    self.assertTrue(hasattr(app, "_poll_scan_queue"))
    self.assertTrue(hasattr(app, "_flush_scan_buffer"))
    app.window.after(0, app.window.destroy)
    app.run()
```

**Step 3: 執行測試**

```bash
python -m pytest test_ui_ctk.py -v
```

**Step 4: Commit**

```bash
git add ui_ctk.py test_ui_ctk.py
git commit -m "feat(ui): 移植 Queue 輪詢與 scan buffer throttle"
```

---

### Task 10: Backend 橋接方法（掃描、下載、樹狀填充）

**目的：** 移植所有與 backend 互動的方法，確保掃描與下載功能正常。

**Files:**
- Modify: `ui_ctk.py`

**Step 1: 從 ui_ttkb.py 搬移以下方法（邏輯不變）**

掃描相關：
- `start_scan()`
- `toggle_scan_pause()`
- `clear_scan_results()`
- `add_folder(folder_url, parent_id)`
- `add_file(file_url, size, file_type, parent_id)`
- `update_progress(scanned, total)`

下載相關：
- `download_selected()`
- `toggle_pause()`
- `_download_file(url, file_path, cancel_event)`
- `_update_download_progress(file_path, progress)`
- `_set_download_status(file_path, text)`

搜尋相關：
- `on_search_filter_changed(*args)`
- `_apply_search_filter(query)`
- `focus_search(event=None)`
- `focus_logs(event=None)`
- `clear_search(event=None)`

**Step 2: 調整 CTkProgressBar 差異**

`ctk.CTkProgressBar` 的 API 與 ttkb.Progressbar 不同：

```python
# ttkb 版本（舊）
self.progress_var.set(value)

# CTk 版本（新）
self.progress_bar.set(value / 100)  # CTkProgressBar 接受 0.0–1.0
```

搜尋 `ui_ttkb.py` 中所有 `progress_var.set` 的地方，改為 `self.progress_bar.set(value / 100)`。

**Step 3: 新增測試**

```python
def test_scan_methods_exist(self):
    import ui_ctk
    for method in ("start_scan", "toggle_scan_pause", "clear_scan_results",
                   "download_selected", "toggle_pause"):
        self.assertTrue(hasattr(ui_ctk.WebsiteCopierCtk, method), f"Missing: {method}")
```

**Step 4: 執行測試**

```bash
python -m pytest test_ui_ctk.py -v
```

**Step 5: Commit**

```bash
git add ui_ctk.py test_ui_ctk.py
git commit -m "feat(ui): 移植 backend 橋接方法（掃描、下載、搜尋）"
```

---

### Task 11: 更新入口 index_ripper.py

**目的：** 讓 `index_ripper.py` 預設啟動 CTk 新版本（`ui_ctk.py`）。

**Files:**
- Modify: `index_ripper.py`（只改主入口的 import，舊 `WebsiteCopier` 類別保留）

**Step 1: 確認現有入口結構**

讀 `index_ripper.py` 最後的 `main()` / `if __name__ == "__main__"` 部分。

**Step 2: 修改入口**

在 `index_ripper.py` 底部找到啟動 `WebsiteCopier` 的地方，改為：

```python
def main() -> int:
    if "--ui-smoke" in sys.argv:
        from ui_ctk import WebsiteCopierCtk
        app = WebsiteCopierCtk(ui_smoke=True)
        app.run()
        print("UI_SMOKE_OK")
        return 0

    from ui_ctk import WebsiteCopierCtk
    app = WebsiteCopierCtk()
    app.run()
    return 0
```

**Step 3: 執行 smoke 測試**

```bash
python index_ripper.py --smoke
```

Expected: `SMOKE_OK`

**Step 4: Commit**

```bash
git add index_ripper.py
git commit -m "feat: 更新入口，預設啟動 CTk 版 UI"
```

---

### Task 12: 整合驗證與清理

**目的：** 完整執行所有測試，確認功能正常，移除不必要的 ttkbootstrap import。

**Files:**
- Modify: `ui_ctk.py`（若有殘留的 ttkb import）
- Modify: `requirements.txt`（可選：將 ttkbootstrap 移至 optional）

**Step 1: 執行完整測試套件**

```bash
python -m pytest test_ui_ctk.py test_ui_theme.py test_ui_downloads.py test_backend.py -v
```

Expected: 全部 PASS

**Step 2: 手動 UI smoke**

```bash
python index_ripper.py --ui-smoke
```

Expected: 視窗出現並正常關閉，輸出 `UI_SMOKE_OK`

**Step 3: 確認 ttkbootstrap 仍在 requirements.txt（保留舊入口用）**

`index_ripper_ttkb.py` 仍可用 ttkb，不移除 dependency，只確認不影響新版。

**Step 4: 最終 commit**

```bash
git add .
git commit -m "test: 整合驗證通過，CTk 遷移完成"
```

---

## 完整功能對照檢查

實作完畢後，逐一對照設計文件的功能清單：

```
docs/plans/2026-03-09-ctk-migration-design.md
```

每個 `[ ]` 項目都應手動驗證可運作。

---

## 已知限制

- `ctk.CTkEntry` 的 `_entry` 屬性是內部 API，`_on_global_url_paste` 中需改用 `focused is self.url_entry` 的比較方式（CTk 5.x 的 entry focus 行為與 tk.Entry 略有不同，需測試後調整）
- `ctk.CTkOptionMenu` 不支援 `readonly` state，threads 輸入值需在 command callback 中做範圍驗證
- `ttk.Treeview` 的 style 在每次 `configure_treeview_style()` 呼叫時會重設 `theme_use("default")`，確保只在 `_build_treeview()` 呼叫一次
