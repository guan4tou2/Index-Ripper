# IndexRipper

[![CI](https://github.com/guan4tou2/Index-Ripper/actions/workflows/ci.yml/badge.svg)](https://github.com/guan4tou2/Index-Ripper/actions/workflows/ci.yml)

[中文說明](README_zh.md)

A graphical tool specifically designed for downloading files from "Index of" pages, making it easy to scan and download all files from directory listings.

## Features

- 📂 Specialized in handling "Index of" type web pages
- 🔍 Recursive directory structure scanning
- ✅ Selective file downloading
- ⏸️ Support pause/resume downloads
- 🌐 HTTP/HTTPS protocol support
- 📊 Real-time download progress display
- 🗂️ Automatic folder structure creation
- 🔄 In-session pause/resume (not persistent resume)

## Main Functions

### Scanning Features

- Automatic website directory structure scanning
- Display file sizes and types
- Support scan pause/resume
- Real-time scanning progress display

### File Type Management

- Automatic identification of all file types
- File type statistics and filtering
- One-click select/deselect specific types
- File type association selection

### Download Management

- Multi-threaded parallel downloads
- Adjustable concurrent download count
- Support pause/resume downloads
- Preserve original directory structure
- Display download progress and speed

### Additional Features

- File sorting (by name/size/type)
- Directory expand/collapse
- Select all/deselect all
- Custom download location

## Usage

1. Enter the website URL to scan
2. Click "Scan" to start website scanning
3. Select file types and specific files to download
4. Choose download location (optional)
5. Click "Download Selected Files" to start downloading

## Quick Operations

- Right-click menu:
  - Select all/Deselect all
  - Expand/Collapse all directories
  
- File type filtering:
  - Click file type checkboxes to select/deselect
  - Use Select all/Deselect all buttons for quick operations

## UI Architecture

IndexRipper uses **CustomTkinter** as its UI framework, providing a modern look with automatic dark/light theme switching.

The file tree uses a custom `FileTree` component (built on `CTkScrollableFrame`) with emoji icons instead of pixel art:
- 📁 folder / 🖼️ image / 📄 document / 🗜️ archive / 💻 code / 🎵 audio / 🎬 video / 📝 text / ⚙️ binary

## System Requirements

- Python **3.11** or higher
- Supports Windows, macOS, Linux

> CustomTkinter bundles its own Tcl/Tk — **no separate system Tkinter installation needed**.

## Installing Dependencies

Prefer uv for faster, reproducible installs:

```bash
# Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install required packages (reads pyproject.toml)
uv sync
```

## Running the Application

```bash
# Run with uv (CustomTkinter UI)
uv run python index_ripper.py

# Quick non-interactive smoke check
uv run python index_ripper.py --smoke

# UI smoke check
uv run python index_ripper.py --ui-smoke

# Deterministic self-test (no real network)
uv run python index_ripper.py --self-test
```

## Download Prebuilt Binaries

You can download prebuilt executables from GitHub Actions artifacts:

- Windows: IndexRipper.exe
- macOS (Intel and Apple Silicon): IndexRipper.app
- Linux (x86_64): IndexRipper

Find them under Actions → "Build Executables (uv + PyInstaller)" → the latest successful run → Artifacts.

- Direct link to workflow runs: [CI Workflow](https://github.com/guan4tou2/Index-Ripper/actions/workflows/ci.yml)
- Latest successful runs: [Actions](https://github.com/guan4tou2/Index-Ripper/actions)

Notes:

- macOS: The app is not signed/notarized. You may need to right-click → Open the first time, or run `xattr -dr com.apple.quarantine IndexRipper.app`.
- Linux: Mark the file executable if needed: `chmod +x ./IndexRipper`.
- Using prebuilt binaries does not require a Python installation.

### macOS: Open and Permissions Guide

If you see "can't be opened" or "cannot be verified":

1) Try Finder (recommended first):

- Right-click `IndexRipper.app` → Open → Click Open in the dialog.
- Or go to System Settings → Privacy & Security → General → Click "Open Anyway" if shown.

1) Remove quarantine attribute (Gatekeeper flag) from Terminal:

```bash
xattr -dr com.apple.quarantine "/path/to/IndexRipper.app"
```

1) Grant executable permission (inside the .app Contents/MacOS):

```bash
chmod +x "/path/to/IndexRipper.app/Contents/MacOS/IndexRipper"
```

1) Launch from Terminal (to observe logs for troubleshooting):

```bash
"/path/to/IndexRipper.app/Contents/MacOS/IndexRipper"
```

Tip: Replace `/path/to` with your actual download location (e.g., `~/Downloads`).

## Build Locally (Packaging)

Build platform-specific executables with uv + PyInstaller.

Windows (PowerShell):

```powershell
uv pip install pyinstaller
uv run pyinstaller --onefile --windowed --icon=app.png --name=IndexRipper `
  --collect-all customtkinter index_ripper.py
```

macOS/Linux (bash):

```bash
uv pip install pyinstaller
# macOS .app
uv run pyinstaller -F --windowed --name=IndexRipper \
  --collect-all customtkinter --icon=app.png index_ripper.py
# Linux single binary
uv run pyinstaller --onefile --windowed --name=IndexRipper \
  --collect-all customtkinter --icon=app.png index_ripper.py
```

## Important Notes

1. Ensure sufficient disk space
2. Adjust concurrent download count when downloading many files
3. Some websites may have access restrictions or require authentication
4. Recommended to use with a stable internet connection

## License

MIT License

## FAQ

### 1. tkinter Related Errors

CustomTkinter bundles its own Tcl/Tk. If issues persist:

- macOS (Homebrew Python): `brew install python-tk@3.11`
- Linux: `sudo apt-get install python3-tk` (Ubuntu/Debian)

### 2. Display Issues

- If interface displays abnormally, it might be a DPI scaling issue
- Windows users can right-click Python.exe → Properties → Compatibility → Change high DPI settings, and enable high DPI scaling override

### 3. Dark/Light Theme

IndexRipper follows the system appearance by default, with automatic switching for macOS and Windows dark mode.
