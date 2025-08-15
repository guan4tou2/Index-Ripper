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
- 🔄 Download resume capability

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

## System Requirements

- Python 3.10 or higher
- Supports Windows, macOS, Linux

### Windows Users

- When installing Python, check "tcl/tk and IDLE"
- If not checked, re-run installer and modify

### macOS Users

```bash
# Install Python and Tkinter using Homebrew
brew install python-tk@3.10
```

### Linux Users

```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch Linux
sudo pacman -S tk
```

## Installing Dependencies

Prefer uv for faster, reproducible installs:

```bash
# Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install required packages
uv pip install -r requirements.txt
```

## Running the Application

```bash
# Run with uv
uv run python index_ripper.py
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
uv pip install -r requirements.txt pyinstaller pillow
uv run pyinstaller --onefile --windowed --icon=app.png --name=IndexRipper `
  --hidden-import tkinter --hidden-import tkinter.ttk index_ripper.py
```

macOS/Linux (bash):

```bash
uv pip install -r requirements.txt pyinstaller pillow
# macOS .app
uv run pyinstaller -F --windowed --name=IndexRipper \
  --hidden-import tkinter --hidden-import tkinter.ttk --icon=app.png index_ripper.py
# Linux single binary
uv run pyinstaller --onefile --windowed --name=IndexRipper \
  --hidden-import tkinter --hidden-import tkinter.ttk --icon=app.png index_ripper.py
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

If you encounter "No module named '_tkinter'" error:

- Windows: Reinstall Python, ensure "tcl/tk and IDLE" is checked
- macOS: Run `brew install python-tk@3.10`
- Linux: Install tkinter package for your distribution

### 2. Display Issues

- If interface displays abnormally, it might be a DPI scaling issue
- Windows users can right-click Python.exe → Properties → Compatibility → Change high DPI settings, and enable high DPI scaling override
