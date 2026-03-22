# Index Ripper 專案重構計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將平放在根目錄的所有 .py 檔案重組為 `src/index_ripper/` 套件結構，移除遺留程式碼，拆分大型模組，統一命名風格，並更新所有相關設定。

**Architecture:** 建立 `src/index_ripper/` Python 套件，將核心邏輯、UI 元件、工具函式分離到子模組中。`index_ripper.py` 中的舊版 `WebsiteCopier` 類別（使用 ttk.Treeview）已被 `ui_ctk.py` 中的 `WebsiteCopierCtk`（使用自訂 RowWidget）完全取代，將移除舊版。`ui_ttkb.py`、`pyside_poc.py`、`index_ripper_ttkb.py` 為遺留/PoC 程式碼，一併移除。

**Tech Stack:** Python 3.11+, CustomTkinter, requests, BeautifulSoup4, pytest, uv, PyInstaller

---

## 檔案結構規劃

### 移除的檔案
- `index_ripper.py` — 包含舊版 `WebsiteCopier` 類別（1434 行，使用 ttk.Treeview），已被 `ui_ctk.py` 的 `WebsiteCopierCtk` 完全取代
- `ui_ttkb.py` — 舊版 ttkbootstrap UI（1387 行）
- `index_ripper_ttkb.py` — ttkbootstrap 進入點
- `pyside_poc.py` — PySide 概念驗證
- `POC_MATRIX.md` — PoC 比較文件

### 新套件結構
```
src/
└── index_ripper/
    ├── __init__.py          # 套件初始化，版本號
    ├── __main__.py          # python -m index_ripper 進入點（--smoke, --self-test, --ui-smoke）
    ├── app.py               # WebsiteCopierCtk 主應用類別（初始化、run、on_closing、backend bridge）
    ├── backend.py           # Backend 類別（掃描、下載邏輯）— 從原 backend.py 移入
    ├── settings.py          # load_settings / save_settings — 從原 settings_store.py 移入
    ├── utils.py             # 工具函式 — 從原 app_utils.py 移入
    ├── self_test.py         # 自測邏輯 — 從原 self_test.py 移入
    └── ui/
        ├── __init__.py      # UI 子套件
        ├── theme.py         # 主題、顏色 tokens、樣式設定 — 從原 ui_theme.py 移入
        ├── downloads.py     # DownloadsPanel — 從原 ui_downloads.py 移入
        ├── filetree.py      # TreeNode、RowWidget、FileTree 相關常量
        └── filters.py       # 檔案類型篩選邏輯
tests/
    ├── __init__.py
    ├── test_backend.py
    ├── test_utils.py        # 合併原 test_app_utils.py + test_security_utils.py
    ├── test_settings.py     # 從原 test_settings_store.py 重新命名
    ├── test_theme.py        # 從原 test_ui_theme.py 重新命名
    ├── test_downloads.py    # 從原 test_ui_downloads.py 重新命名
    └── test_app_smoke.py    # 從原 test_ui_ctk.py 重新命名
```

### 修改的設定檔
- `pyproject.toml` — 更新 entry point、testpaths
- `macos.spec` — 更新 Analysis 路徑
- `.github/workflows/ci.yml` — 更新測試指令路徑
- `.gitignore` — 確認 src/ 結構相容

---

## Task 1: 建立套件骨架並移動工具模組

**Files:**
- Create: `src/index_ripper/__init__.py`
- Create: `src/index_ripper/utils.py`
- Create: `src/index_ripper/settings.py`
- Create: `src/index_ripper/self_test.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: 建立目錄結構**

```bash
mkdir -p src/index_ripper/ui
mkdir -p tests
```

- [ ] **Step 2: 建立 `src/index_ripper/__init__.py`**

```python
"""Index Ripper — download files from directory listing pages."""

__version__ = "0.1.0"
```

- [ ] **Step 3: 移動 `app_utils.py` → `src/index_ripper/utils.py`**

將 `app_utils.py` 的所有內容複製到 `src/index_ripper/utils.py`，保持所有函式不變。

- [ ] **Step 4: 移動 `settings_store.py` → `src/index_ripper/settings.py`**

將 `settings_store.py` 的所有內容複製到 `src/index_ripper/settings.py`。

- [ ] **Step 5: 移動 `self_test.py` → `src/index_ripper/self_test.py`**

將 `self_test.py` 的所有內容複製到 `src/index_ripper/self_test.py`。

- [ ] **Step 6: 更新 `pyproject.toml`**

新增 build-system 設定（src layout 必需），更新 entry point，移除 ttkbootstrap 依賴：

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/index_ripper"]

[project.scripts]
index-ripper = "index_ripper.app:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

移除 `ttkbootstrap` 依賴：
```toml
dependencies = [
    "requests>=2.31.0,<3.0.0",
    "beautifulsoup4>=4.12.0,<5.0.0",
    "urllib3>=2.0.0,<3.0.0",
    "customtkinter>=5.2.0,<6.0.0",
]
```

- [ ] **Step 6b: 執行 `uv sync` 安裝新套件結構**

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv sync --extra dev`
Expected: 成功安裝，`index_ripper` 套件可被 import

- [ ] **Step 7: 執行測試確認工具模組可獨立 import**

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv run python -c "from index_ripper.utils import sanitize_filename; print('OK')"`
Expected: `OK`

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv run python -c "from index_ripper.settings import load_settings; print('OK')"`
Expected: `OK`

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv run python -c "from index_ripper.self_test import run_self_test; print('OK')"`
Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add src/ pyproject.toml
git commit -m "refactor: create src/index_ripper package skeleton with utils, settings, self_test"
```

---

## Task 2: 移動 backend 模組

**Files:**
- Create: `src/index_ripper/backend.py`
- Modify: `src/index_ripper/utils.py` (確認 import 路徑)

- [ ] **Step 1: 複製 `backend.py` → `src/index_ripper/backend.py`**

更新 import 語句：
```python
# 原本
from app_utils import cleanup_partial_file, is_url_in_scope

# 改為
from index_ripper.utils import cleanup_partial_file, is_url_in_scope
```

其餘 Backend 類別內容完全不變。

- [ ] **Step 2: 驗證 import**

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv run python -c "from index_ripper.backend import Backend; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/index_ripper/backend.py
git commit -m "refactor: move Backend class to src/index_ripper/backend.py"
```

---

## Task 3: 移動 UI 子模組（theme、downloads）

**Files:**
- Create: `src/index_ripper/ui/__init__.py`
- Create: `src/index_ripper/ui/theme.py`
- Create: `src/index_ripper/ui/downloads.py`

- [ ] **Step 1: 建立 `src/index_ripper/ui/__init__.py`**

```python
"""Index Ripper UI components."""
```

- [ ] **Step 2: 複製 `ui_theme.py` → `src/index_ripper/ui/theme.py`**

內容完全不變（沒有 internal import 需要更新）。

- [ ] **Step 3: 複製 `ui_downloads.py` → `src/index_ripper/ui/downloads.py`**

內容完全不變（沒有 internal import 需要更新）。

- [ ] **Step 4: 驗證 import**

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv run python -c "from index_ripper.ui.theme import ui_tokens; print('OK')"`
Expected: `OK`

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv run python -c "from index_ripper.ui.downloads import DownloadsPanel; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/index_ripper/ui/
git commit -m "refactor: move theme and downloads UI modules to src/index_ripper/ui/"
```

---

## Task 4: 拆分 ui_ctk.py — 抽取 filetree 模組

**Files:**
- Create: `src/index_ripper/ui/filetree.py`

`ui_ctk.py` 的前 180 行包含 `TreeNode` dataclass、`_EMOJI_ICONS` 常量、顏色常量、`RowWidget` 類別和 `should_skip_file_row` 函式。這些是自成一體的檔案樹資料模型和視覺元件。

- [ ] **Step 1: 建立 `src/index_ripper/ui/filetree.py`**

從 `ui_ctk.py` 第 1-184 行提取以下內容：
- `TreeNode` dataclass
- `_EMOJI_ICONS` 字典
- `_BG_NORMAL`, `_BG_HOVER`, `_BG_CHECKED`, `_BG_CHECKED_HOVER` 顏色常量
- `RowWidget` 類別
- `should_skip_file_row` 函式

加上必要的 import：
```python
from __future__ import annotations

from dataclasses import dataclass, field

import customtkinter as ctk
```

- [ ] **Step 2: 驗證 import**

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv run python -c "from index_ripper.ui.filetree import TreeNode, RowWidget; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/index_ripper/ui/filetree.py
git commit -m "refactor: extract TreeNode, RowWidget into ui/filetree.py"
```

---

## Task 5: 拆分 ui_ctk.py — 抽取 filters 模組

**Files:**
- Create: `src/index_ripper/ui/filters.py`

`WebsiteCopierCtk` 中以下方法與檔案類型篩選有關，可獨立為 mixin 或輔助類別：
- `_add_file_type_filter`
- `_on_type_filter_changed`
- `select_all_types`
- `deselect_all_types`
- `_bind_hscroll_wheel`

- [ ] **Step 1: 建立 `src/index_ripper/ui/filters.py`**

建立 `FileTypeFilterMixin` 類別，包含上述方法。這些方法依賴 `self.file_types`, `self.file_type_counts`, `self.file_type_widgets`, `self.filters_container`, `self.tree_nodes`, `self.full_tree_backup` 等屬性，作為 mixin 使用時由主應用類別提供。

```python
"""File type filter UI logic (mixin for the main app)."""
from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

from index_ripper.utils import normalize_extension


class FileTypeFilterMixin:
    """Mixin providing file-type checkbox filter behaviour."""

    def _add_file_type_filter(self, ext: str) -> None:
        ...  # 從 ui_ctk.py 第 1479-1497 行搬入

    def _on_type_filter_changed(self, ext: str) -> None:
        ...  # 從 ui_ctk.py 第 1499-1511 行搬入
        # 注意：此方法呼叫 self._rebuild_visible() 和 self._sync_rows()
        # 這些方法定義在 WebsiteCopierCtk (app.py) 中，由 mixin 透過 self 動態解析

    def select_all_types(self) -> None:
        ...  # 從 ui_ctk.py 第 1449-1451 行搬入

    def deselect_all_types(self) -> None:
        ...  # 從 ui_ctk.py 第 1453-1455 行搬入

    def _bind_hscroll_wheel(self, widget) -> None:
        ...  # 從 ui_ctk.py 第 1457-1477 行搬入
```

- [ ] **Step 2: 驗證 import**

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv run python -c "from index_ripper.ui.filters import FileTypeFilterMixin; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/index_ripper/ui/filters.py
git commit -m "refactor: extract FileTypeFilterMixin into ui/filters.py"
```

---

## Task 6: 建立主應用模組 app.py

**Files:**
- Create: `src/index_ripper/app.py`

這是最關鍵的一步。從 `ui_ctk.py` 的 `WebsiteCopierCtk` 類別搬入 `app.py`，同時：
- 從 `ui.filetree` import `TreeNode`, `RowWidget`, `should_skip_file_row`
- 從 `ui.filters` import `FileTypeFilterMixin` 並作為 mixin
- 更新所有 internal import 為套件路徑

- [ ] **Step 1: 建立 `src/index_ripper/app.py`**

```python
"""Main application window."""
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

from index_ripper.utils import (
    build_download_path,
    default_download_folder,
    normalize_extension,
    rebuild_executor,
    safe_join,
    sanitize_filename,
)
from index_ripper.backend import Backend
from index_ripper.ui.downloads import DownloadsPanel
from index_ripper.ui.theme import (
    apply_app_theme,
    configure_action_button_styles,
    ui_tokens,
)
from index_ripper.ui.filetree import TreeNode, RowWidget, should_skip_file_row
from index_ripper.ui.filters import FileTypeFilterMixin


class WebsiteCopierCtk(FileTypeFilterMixin):
    ...  # 從 ui_ctk.py 第 187-1517 行搬入（排除 TreeNode、RowWidget、should_skip_file_row、
         # FileTypeFilterMixin 已抽出的方法）


def main():
    app = WebsiteCopierCtk()
    app.run()
```

- [ ] **Step 2: 建立 `src/index_ripper/__main__.py`**

```python
"""Entry point for `python -m index_ripper`."""
import sys


def _main() -> None:
    if "--smoke" in sys.argv:
        print("SMOKE_OK")
        raise SystemExit(0)

    if "--self-test" in sys.argv:
        from index_ripper.self_test import run_self_test

        result = run_self_test()
        print(
            f"SELF_TEST_OK total={result.total} files={result.files} dirs={result.directories}"
        )
        raise SystemExit(0)

    from index_ripper.utils import configure_tk_libraries
    configure_tk_libraries()

    if "--ui-smoke" in sys.argv:
        from index_ripper.app import WebsiteCopierCtk

        app = WebsiteCopierCtk(ui_smoke=True)
        app.window.after(0, app.window.destroy)
        app.run()
        print("UI_SMOKE_OK")
        raise SystemExit(0)

    from index_ripper.app import main
    main()


if __name__ == "__main__":
    _main()
```

- [ ] **Step 3: 驗證應用可啟動**

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv run python -m index_ripper --smoke`
Expected: `SMOKE_OK`

- [ ] **Step 4: Commit**

```bash
git add src/index_ripper/app.py src/index_ripper/__main__.py
git commit -m "refactor: create main app module with WebsiteCopierCtk and __main__ entry point"
```

---

## Task 7: 遷移並合併測試檔案

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_backend.py`
- Create: `tests/test_utils.py`
- Create: `tests/test_settings.py`
- Create: `tests/test_theme.py`
- Create: `tests/test_downloads.py`
- Create: `tests/test_app_smoke.py`

- [ ] **Step 1: 建立 `tests/__init__.py`**

空檔案。

- [ ] **Step 2: 遷移 `test_backend.py` → `tests/test_backend.py`**

更新 import：
```python
# 原本
from backend import Backend

# 改為
from index_ripper.backend import Backend
```

- [ ] **Step 3: 合併 `test_app_utils.py` + `test_security_utils.py` → `tests/test_utils.py`**

更新 import：
```python
# 原本
from app_utils import ...

# 改為
from index_ripper.utils import ...
```

將兩個檔案的測試類別合併到同一檔案中。

- [ ] **Step 4: 遷移其餘測試**

- `test_settings_store.py` → `tests/test_settings.py`（import 改為 `from index_ripper.settings import ...`）
- `test_ui_theme.py` → `tests/test_theme.py`
  - 原本用 `import ui_theme` 再 `ui_theme.action_button_style_name(...)` 的寫法，改為 `from index_ripper.ui import theme` 再 `theme.action_button_style_name(...)`
- `test_ui_downloads.py` → `tests/test_downloads.py`
  - 同上，`import ui_downloads` 改為 `from index_ripper.ui import downloads`，呼叫改為 `downloads.download_status_state(...)`
- `test_ui_ctk.py` → `tests/test_app_smoke.py`
  - **重點**：此檔案大量使用 `import ui_ctk`、`importlib.import_module("ui_ctk")` 和 `importlib.reload(mod)`
  - 所有 `"ui_ctk"` 字串需改為 `"index_ripper.app"`
  - `import ui_ctk` 改為 `from index_ripper import app as ui_ctk`
  - `importlib.import_module("ui_ctk")` 改為 `importlib.import_module("index_ripper.app")`
  - `import ui_ctk, importlib` 改為 `from index_ripper import app as ui_ctk; import importlib`

- [ ] **Step 5: 執行所有測試**

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv run python -m pytest tests/ -v`
Expected: 所有測試通過

- [ ] **Step 6: Commit**

```bash
git add tests/
git commit -m "refactor: migrate and consolidate tests to tests/ directory"
```

---

## Task 8: 刪除舊檔案

**Files:**
- Delete: `index_ripper.py`
- Delete: `ui_ctk.py`
- Delete: `ui_ttkb.py`
- Delete: `index_ripper_ttkb.py`
- Delete: `pyside_poc.py`
- Delete: `POC_MATRIX.md`
- Delete: `backend.py`
- Delete: `app_utils.py`
- Delete: `settings_store.py`
- Delete: `self_test.py`
- Delete: `ui_theme.py`
- Delete: `ui_downloads.py`
- Delete: `test_backend.py`
- Delete: `test_app_utils.py`
- Delete: `test_security_utils.py`
- Delete: `test_settings_store.py`
- Delete: `test_ui_theme.py`
- Delete: `test_ui_downloads.py`
- Delete: `test_ui_ttkb.py`
- Delete: `test_ui_ctk.py`

- [ ] **Step 1: 刪除遺留程式碼（UI 和 PoC）**

```bash
git rm index_ripper.py ui_ttkb.py index_ripper_ttkb.py pyside_poc.py POC_MATRIX.md
```

- [ ] **Step 2: 刪除已遷移到 src/ 的舊模組**

```bash
git rm ui_ctk.py backend.py app_utils.py settings_store.py self_test.py ui_theme.py ui_downloads.py
```

- [ ] **Step 3: 刪除已遷移到 tests/ 的舊測試**

```bash
git rm test_backend.py test_app_utils.py test_security_utils.py test_settings_store.py test_ui_theme.py test_ui_downloads.py test_ui_ttkb.py test_ui_ctk.py
```

- [ ] **Step 4: 執行所有測試確認無殘留依賴**

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv run python -m pytest tests/ -v`
Expected: 所有測試通過

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv run python -m index_ripper --smoke`
Expected: `SMOKE_OK`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove legacy files and old root-level modules"
```

---

## Task 9: 更新建置與 CI 設定

**Files:**
- Modify: `macos.spec`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/build.yml` (如有需要)

- [ ] **Step 1: 更新 `macos.spec`**

```python
a = Analysis(
    ["src/index_ripper/__main__.py"],
    pathex=["src"],                      # <-- 必須加上，讓 PyInstaller 找到 index_ripper 套件
    ...
    hiddenimports=["tkinter", "tkinter.ttk", "index_ripper"],
    ...
)
```

- [ ] **Step 2: 更新 `.github/workflows/ci.yml`**

測試指令改為：
```yaml
- name: Run unit tests
  run: uv run python -m pytest tests/ -v
```

更新所有三個平台的 PyInstaller build 指令（Windows、macOS、Linux），全部加上 `--paths src`：

Windows build:
```yaml
run: |
  uv run pyinstaller --onefile --windowed --icon=app.png --name=IndexRipper \
    --paths src --collect-all customtkinter src/index_ripper/__main__.py
```

macOS build:
```yaml
run: |
  uv run pyinstaller -F --windowed --name=IndexRipper \
    --paths src --collect-all customtkinter --icon=app.png src/index_ripper/__main__.py
```

Linux build:
```yaml
run: |
  uv run pyinstaller --onefile --windowed --name=IndexRipper \
    --paths src --collect-all customtkinter --icon=app.png src/index_ripper/__main__.py
```

- [ ] **Step 3: 更新 `pyproject.toml`（如果 Task 1 還沒做完）**

確認 ttkbootstrap 已從 dependencies 移除。

- [ ] **Step 4: 驗證 smoke test**

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv run python -m index_ripper --smoke`
Expected: `SMOKE_OK`

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv run python -m index_ripper --self-test`
Expected: `SELF_TEST_OK total=... files=... dirs=...`

- [ ] **Step 5: Commit**

```bash
git add macos.spec .github/workflows/ pyproject.toml
git commit -m "build: update CI, PyInstaller, and pyproject for new package structure"
```

---

## Task 10: 最終驗證與清理

**Files:**
- Modify: `.gitignore` (如需要)
- Modify: `README.md` (更新安裝/運行指令)

- [ ] **Step 1: 執行完整測試套件**

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv run python -m pytest tests/ -v`
Expected: 所有測試通過

- [ ] **Step 2: 驗證所有進入點**

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv run python -m index_ripper --smoke`
Expected: `SMOKE_OK`

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv run python -m index_ripper --self-test`
Expected: `SELF_TEST_OK ...`

- [ ] **Step 3: 更新 README.md 中的使用說明**

將 `python index_ripper.py` 改為 `python -m index_ripper` 或 `index-ripper`。

- [ ] **Step 4: 確認 `uv.lock` 同步（移除 ttkbootstrap）**

Run: `cd /Users/guantou/Desktop/Index-Ripper && uv lock`

- [ ] **Step 5: 最終 Commit**

```bash
git add -A
git commit -m "docs: update README for new package structure"
```
