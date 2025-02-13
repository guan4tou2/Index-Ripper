# IndexRipper (索引擷取器)

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

1. 輸入要掃描的網站URL
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
- 支援 Windows、macOS 系統

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

```bash
# 安裝所需套件
pip install -r requirements.txt
```

## 執行方式

```bash
python website_copier.py
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
