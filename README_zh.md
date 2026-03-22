# Index Ripper

[![CI](https://github.com/guan4tou2/Index-Ripper/actions/workflows/ci.yml/badge.svg)](https://github.com/guan4tou2/Index-Ripper/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[English](README.md)

從 "Index of" 目錄列表頁面下載檔案的桌面工具。掃描網站、瀏覽檔案樹、按類型篩選，下載你需要的檔案。

## 功能

- 遞迴掃描目錄結構，支援暫停/繼續
- 檔案樹：展開/收合、搜尋、類型篩選
- 多執行緒下載（1-10 並行），逐檔進度顯示
- 暫停/繼續/取消個別下載
- 伺服器錯誤自動重試（3 次，指數退避）
- 保留原始目錄結構
- 多網站任務佇列（Electron）— 用分頁同時掃描/下載多個網站
- 檔案預覽（圖片 + 文字），雙擊即可（Electron）
- Shift+Click 範圍選取，按名稱/大小/類型排序（Electron）
- 深色模式 UI

## 兩個版本

| | Python (CustomTkinter) | Electron (React + TypeScript) |
|---|---|---|
| 位置 | `src/index_ripper/` | `electron-app/` |
| UI | CustomTkinter + emoji 圖示 | React + Tailwind + shadcn/ui |
| 後端 | Python requests + BeautifulSoup | Node.js http + cheerio |
| 多網站分頁 | 無 | 有 |
| 檔案預覽 | 無 | 有（圖片 + 文字）|
| 打包 | PyInstaller | electron-builder |

## 快速開始

### Electron（推薦）

```bash
cd electron-app
npm install
npm run dev
```

### Python

```bash
# 安裝 uv（僅需一次）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安裝並執行
uv sync
uv run python -m index_ripper
```

## 下載預建檔案

從 [Releases](https://github.com/guan4tou2/Index-Ripper/releases) 或 [CI Artifacts](https://github.com/guan4tou2/Index-Ripper/actions/workflows/ci.yml) 下載：

| 平台 | Electron | Python |
|------|----------|--------|
| Windows | `.exe`（NSIS 安裝程式）| `.exe`（PyInstaller）|
| macOS | `.dmg`（Universal）| `.app` |
| Linux | `.AppImage` | 執行檔 |

> **macOS 注意：** 應用程式未簽章。首次啟動：右鍵 → 打開，或執行 `xattr -dr com.apple.quarantine IndexRipper.app`。

## 使用方式

1. 輸入指向 "Index of" 目錄列表的 URL
2. 點擊 **Scan** 掃描檔案和目錄
3. 瀏覽檔案樹、按類型篩選、按名稱搜尋
4. 選取檔案（點擊、Shift+Click 範圍選取、Ctrl+A 全選）
5. 點擊 **Download** 開始下載

### 快捷鍵

| 快捷鍵 | 動作 |
|--------|------|
| `Ctrl/Cmd + F` | 搜尋 |
| `Ctrl/Cmd + A` | 全選 |
| `Escape` | 清除搜尋 |
| `Enter` | 開始掃描（URL 輸入框聚焦時）|
| 雙擊 | 預覽檔案（Electron）|

## 從原始碼建置

### Electron

```bash
cd electron-app
npm install

# 開發模式
npm run dev

# 建置當前平台
npm run build:mac    # macOS .dmg
npm run build:win    # Windows .exe
npm run build:linux  # Linux .AppImage
```

### Python

```bash
uv sync
uv pip install pyinstaller

# macOS
uv run pyinstaller -F --windowed --name=IndexRipper \
  --collect-all customtkinter --icon=app.png --paths src src/index_ripper/__main__.py

# Windows
uv run pyinstaller --onefile --windowed --icon=app.png --name=IndexRipper \
  --collect-all customtkinter --paths src src/index_ripper/__main__.py

# Linux
uv run pyinstaller --onefile --windowed --name=IndexRipper \
  --collect-all customtkinter --icon=app.png --paths src src/index_ripper/__main__.py
```

## 專案結構

```
Index-Ripper/
├── electron-app/              # Electron 版本
│   ├── src/main/              #   主程序（掃描器、下載器、IPC）
│   ├── src/renderer/          #   React UI
│   ├── src/shared/            #   共用型別
│   └── src/preload/           #   Context bridge
├── src/index_ripper/          # Python 版本
│   ├── app.py                 #   主 UI（CustomTkinter）
│   ├── backend.py             #   掃描器 & 下載器
│   └── ui/                    #   UI 元件
├── tests/                     # Python 測試
└── docs/                      # 設計規格 & 計畫
```

## 貢獻

1. Fork 此專案
2. 建立功能分支（`git checkout -b feat/my-feature`）
3. 提交變更
4. Push 並開啟 Pull Request

## 授權

[MIT](LICENSE)
