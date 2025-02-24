# IndexRipper

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
- Supports Windows, macOS systems

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

```bash
# Install required packages
pip install -r requirements.txt
```

## Running the Application

```bash
python website_copier.py
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


