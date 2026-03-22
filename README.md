# Index Ripper

[![CI](https://github.com/guan4tou2/Index-Ripper/actions/workflows/ci.yml/badge.svg)](https://github.com/guan4tou2/Index-Ripper/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[中文說明](README_zh.md)

A desktop tool for downloading files from "Index of" directory listing pages. Scan a website, browse its file tree, filter by type, and download what you need.

## Features

- Recursive directory scanning with pause/resume
- File tree with expand/collapse, search, and type filtering
- Multi-threaded downloads (1-10 concurrent) with per-file progress
- Pause/resume/cancel individual downloads
- Automatic retry on server errors (3 attempts, exponential backoff)
- Preserves original directory structure
- Multi-site task queue (Electron) — scan/download multiple sites in tabs
- File preview (images + text) via double-click (Electron)
- Shift+click range selection and sort by name/size/type (Electron)
- Dark mode UI

## Two Versions

| | Python (CustomTkinter) | Electron (React + TypeScript) |
|---|---|---|
| Location | `src/index_ripper/` | `electron-app/` |
| UI | CustomTkinter with emoji icons | React + Tailwind + shadcn/ui |
| Backend | Python requests + BeautifulSoup | Node.js http + cheerio |
| Multi-site tabs | No | Yes |
| File preview | No | Yes (images + text) |
| Build | PyInstaller | electron-builder |

## Quick Start

### Electron (recommended)

```bash
cd electron-app
npm install
npm run dev
```

### Python

```bash
# Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install and run
uv sync
uv run python -m index_ripper
```

## Download Prebuilt Binaries

Download from [Releases](https://github.com/guan4tou2/Index-Ripper/releases) or [CI Artifacts](https://github.com/guan4tou2/Index-Ripper/actions/workflows/ci.yml):

| Platform | Electron | Python |
|----------|----------|--------|
| Windows | `.exe` (NSIS installer) | `.exe` (PyInstaller) |
| macOS | `.dmg` (Universal) | `.app` |
| Linux | `.AppImage` | Binary |

> **macOS note:** The app is unsigned. First launch: right-click -> Open, or run `xattr -dr com.apple.quarantine IndexRipper.app`.

## Usage

1. Enter a URL pointing to an "Index of" directory listing
2. Click **Scan** to discover files and directories
3. Browse the file tree, filter by type, search by name
4. Select files (click, Shift+click for range, Ctrl+A for all)
5. Click **Download** to start downloading

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + F` | Focus search |
| `Ctrl/Cmd + A` | Select all files |
| `Escape` | Clear search |
| `Enter` | Start scan (when URL input focused) |
| Double-click | Preview file (Electron) |

## Build From Source

### Electron

```bash
cd electron-app
npm install

# Development
npm run dev

# Build for current platform
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

## Project Structure

```
Index-Ripper/
├── electron-app/              # Electron version
│   ├── src/main/              #   Main process (scanner, downloader, IPC)
│   ├── src/renderer/          #   React UI
│   ├── src/shared/            #   Shared types
│   └── src/preload/           #   Context bridge
├── src/index_ripper/          # Python version
│   ├── app.py                 #   Main UI (CustomTkinter)
│   ├── backend.py             #   Scanner & downloader
│   └── ui/                    #   UI components
├── tests/                     # Python tests
└── docs/                      # Design specs & plans
```

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Commit your changes
4. Push and open a Pull Request

## License

[MIT](LICENSE)
