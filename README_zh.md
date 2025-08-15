# IndexRipper (索引擷取器)

[![CI](https://github.com/guan4tou2/Index-Ripper/actions/workflows/ci.yml/badge.svg)](https://github.com/guan4tou2/Index-Ripper/actions/workflows/ci.yml)

[English](README.md)

這是一個專門用於下載 Index of 頁面檔案的圖形化工具，可以輕鬆掃描並下載目錄列表中的所有檔案。

## 功能特點

- 📂 專門處理 Index of 類型網頁
- 🔍 遞迴掃描目錄結構
- ✅ 可選擇性下載檔案
- ⏸️ 支援暫停/繼續下載
- 🌐 支援 HTTP/HTTPS 協議
- 📊 即時顯示下載進度
- 🗂️ 自動建立資料夾結構
- 🔄 支援續傳功能

## 主要功能

### 掃描功能

- 自動掃描網站目錄結構
- 顯示檔案大小和類型
- 支援掃描暫停/繼續
- 即時顯示掃描進度

### 檔案類型管理

- 自動識別所有檔案類型
- 檔案類型統計和過濾
- 一鍵選擇/取消選擇特定類型
- 檔案類型關聯選擇

### 下載管理

- 多線程並行下載
- 可調整同時下載數量
- 支援暫停/繼續下載
- 保持原始目錄結構
- 顯示下載進度和速度

### 其他功能

- 檔案排序（按名稱/大小/類型）
- 目錄展開/收起
- 全選/取消全選
- 自定義下載位置

## 使用方法

1. 輸入要掃描的網站 URL
2. 點擊「掃描」開始掃描網站
3. 選擇要下載的檔案類型和具體檔案
4. 選擇下載位置（可選）
5. 點擊「下載選擇的檔案」開始下載

## 快捷操作

- 右鍵選單：
  - 全選/取消全選
  - 展開/收起所有目錄
  
- 檔案類型過濾：
  - 點擊檔案類型勾選框選擇/取消選擇
  - 使用全選/取消全選按鈕快速操作

## 系統需求

- Python 3.10 或更高版本
- 支援 Windows、macOS、Linux 系統

### Windows 使用者

- Python 安裝時請勾選 "tcl/tk and IDLE"
- 如果沒有勾選，可以重新執行安裝程式並修改

### macOS 使用者

```bash
# 使用 Homebrew 安裝 Python 和 Tkinter
brew install python-tk@3.10
```

### Linux 使用者

```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch Linux
sudo pacman -S tk
```

## 安裝依賴

建議使用 uv 來進行快速且可重現的安裝：

```bash
# 安裝 uv（僅需一次）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安裝所需套件
uv pip install -r requirements.txt
```

## 執行方式

```bash
# 使用 uv 執行
uv run python index_ripper.py
```

## 下載已編譯執行檔

可於 GitHub Actions 的 artifacts 下載預先編譯好的執行檔：

- Windows：IndexRipper.exe
- macOS（Intel 與 Apple Silicon）：IndexRipper.app
- Linux（x86_64）：IndexRipper

位置：Actions → 「Build Executables (uv + PyInstaller)」→ 最近一次成功執行 → Artifacts。

- 直接前往工作流程列表：[CI Workflow](https://github.com/guan4tou2/Index-Ripper/actions/workflows/ci.yml)
- 最近成功記錄列表：[Actions](https://github.com/guan4tou2/Index-Ripper/actions)

注意事項：

- macOS：未簽章/未 notarize。首次打開可能需右鍵→開啟，或執行 `xattr -dr com.apple.quarantine IndexRipper.app`。
- Linux：如需，請先賦予執行權限：`chmod +x ./IndexRipper`。
- 使用預編譯檔不需要安裝 Python。

### macOS 開啟與權限教學

若出現「無法打開應用程式」或「無法驗證開發者」：

1) 使用 Finder 的方式（建議先試）

- 右鍵點選 `IndexRipper.app` → 選擇「打開」→ 在出現的對話框中再按一次「打開」。
- 若在「系統設定 → 隱私權與安全性 → 一般」看到「仍要打開」，請點選它。

1) 從終端機移除隔離屬性（Gatekeeper 標記）

```bash
xattr -dr com.apple.quarantine "/path/to/IndexRipper.app"
```

1) 賦予執行權限（進入 .app 內部的 Contents/MacOS）

```bash
chmod +x "/path/to/IndexRipper.app/Contents/MacOS/IndexRipper"
```

1) 直接從終端機啟動（可觀察輸出訊息，有助除錯）

```bash
"/path/to/IndexRipper.app/Contents/MacOS/IndexRipper"
```

提示：請將上述的 `/path/to` 替換為實際下載位置（例如 `~/Downloads`）。

## 本地打包（Packaging）

使用 uv + PyInstaller 打包成各平台可執行檔。

Windows（PowerShell）：

```powershell
uv pip install -r requirements.txt pyinstaller pillow
uv run pyinstaller --onefile --windowed --icon=app.png --name=IndexRipper `
  --hidden-import tkinter --hidden-import tkinter.ttk index_ripper.py
```

macOS/Linux（bash）：

```bash
uv pip install -r requirements.txt pyinstaller pillow
# macOS .app
uv run pyinstaller -F --windowed --name=IndexRipper \
  --hidden-import tkinter --hidden-import tkinter.ttk --icon=app.png index_ripper.py
# Linux 單一執行檔
uv run pyinstaller --onefile --windowed --name=IndexRipper \
  --hidden-import tkinter --hidden-import tkinter.ttk --icon=app.png index_ripper.py
```

## 注意事項

1. 請確保有足夠的硬碟空間
2. 下載大量檔案時建議調整同時下載數量
3. 某些網站可能有訪問限制或需要認證
4. 建議在穩定的網路環境下使用

## 授權協議

MIT License

## 常見問題

### 1. tkinter 相關錯誤

如果遇到 "No module named '_tkinter'" 錯誤：

- Windows：重新安裝 Python，確保勾選 "tcl/tk and IDLE"
- macOS：執行 `brew install python-tk@3.10`
- Linux：安裝對應發行版的 tkinter 套件

### 2. 畫面顯示問題

- 如果介面顯示異常，可能是 DPI 縮放問題
- Windows 用戶可以右鍵點擊 Python.exe → 內容 → 相容性 → 變更高 DPI 設定，並啟用高 DPI 縮放覆寫
