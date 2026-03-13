# Design: 遷移 UI 至 CustomTkinter

日期：2026-03-09
狀態：已核准

## 背景

目前 UI 混用 ttkbootstrap（`ui_ttkb.py`）和 CustomTkinter（`ui_downloads.py`），造成以下問題：
- 兩套主題系統互相干擾，跨平台外觀不一致
- `ui_theme.py` 的 design token 是 CTk 格式，卻套用在 ttkbootstrap widget 上
- 維護成本高，新功能難以保持風格一致

## 目標

- 統一使用 CustomTkinter 作為唯一 UI 框架
- 保留所有現有功能，一個都不減
- 確保多執行緒安全（Queue + `after()` 模式）
- 好看、輕量、跨平台一致

## 架構

### 檔案變動

| 檔案 | 動作 |
|---|---|
| `ui_ctk.py` | **新增**，主 UI 類別，取代 `ui_ttkb.py` |
| `ui_ttkb.py` | 保留不動（歷史參考），入口不再指向它 |
| `ui_downloads.py` | 小幅清理，確保與新主題一致 |
| `ui_theme.py` | 移除 ttkbootstrap 相關函式，保留 CTk token + Treeview 樣式 |
| `index_ripper.py` | 更新入口，改為載入 `ui_ctk.py` |
| `index_ripper_ttkb.py` | 保留，作為 ttkb 備用入口 |

### Widget 對應

| ttkbootstrap | CustomTkinter | 備注 |
|---|---|---|
| `ttkb.Window` | `ctk.CTk()` | |
| `ttkb.Frame` | `ctk.CTkFrame` | |
| `ttkb.Button` | `ctk.CTkButton` | |
| `ttkb.Label` | `ctk.CTkLabel` | |
| `ttkb.Entry` | `ctk.CTkEntry` | |
| `ttkb.Progressbar` | `ctk.CTkProgressBar` | |
| `ttkb.Notebook` | `ctk.CTkTabview` | |
| `ttkb.Combobox` | `ctk.CTkOptionMenu` | Threads 選單 |
| `ttkb.Treeview` | `ttk.Treeview`（保留）| CTk 無此 widget |
| `tk.Text` | `ctk.CTkTextbox` | Logs |
| `tk.Checkbutton` | `ctk.CTkCheckBox` | 檔案類型篩選 |
| Scrollbar | `ctk.CTkScrollableFrame` | Downloads list |

> `ttk.Treeview` 是唯一例外，透過 `ttk.Style()` 配合 CTk 主題色統一外觀。

## 功能清單（必須全部實作）

### 輸入區
- [ ] URL 輸入框
- [ ] Cmd/Ctrl+V paste 處理（含右鍵選單）
- [ ] 全域 paste 偵測（焦點在 URL 欄時自動填入）
- [ ] Status label（Ready / Scanning / Error 等狀態）

### 掃描控制
- [ ] Scan 按鈕
- [ ] Pause Scan / Resume Scan 按鈕（掃描中才啟用）
- [ ] Clear 按鈕
- [ ] Ctrl+F 聚焦搜尋欄
- [ ] Ctrl+L 聚焦 Logs

### 篩選區
- [ ] 動態產生 Checkbox（依掃描到的副檔名）
- [ ] Select All Types / Deselect All Types 按鈕
- [ ] 水平可捲動容器（檔案類型多時）

### 下載控制
- [ ] Download Selected 按鈕
- [ ] Pause / Resume 下載按鈕（下載中才啟用）
- [ ] Choose Folder 按鈕
- [ ] Threads 數量選單（1–10）
- [ ] Hide / Show Panels 切換

### Treeview（掃描結果）
- [ ] 欄位：Path / Size / Type（full_path 隱藏）
- [ ] 搜尋即時過濾
- [ ] 欄位排序（點標題）
- [ ] 行勾選（✔ 標記，`checked` tag）
- [ ] Cmd/Ctrl+A 全選
- [ ] Space 切換勾選
- [ ] Enter 確認
- [ ] 拖曳多選
- [ ] 右鍵選單（Select All / Deselect All / Expand All / Collapse All）

### 進度區
- [ ] 整體進度條（`ctk.CTkProgressBar`）
- [ ] 進度文字 label

### Tabs 面板
- [ ] CTkTabview，兩個 tab：Downloads / Logs
- [ ] Downloads tab：每項有名稱、進度條、狀態文字、取消按鈕
- [ ] Logs tab：`ctk.CTkTextbox`，可捲動，`log_message()` 方法

### 執行緒安全
- [ ] Queue + `window.after()` 輪詢模式完整保留
- [ ] `scan_item_buffer` 批次 flush（throttle）
- [ ] `files_dict_lock` / `folders_dict_lock` 保留

### 其他
- [ ] `--ui-smoke` 模式（最小化 UI，不啟動完整介面）
- [ ] `INDEX_RIPPER_DEBUG` 環境變數支援
- [ ] `INDEX_RIPPER_MODAL_DIALOGS` 環境變數支援
- [ ] `on_closing` 視窗關閉處理
- [ ] 所有鍵盤快捷鍵綁定

## 執行緒安全說明

所有背景執行緒（掃描、下載）只能寫入 Queue，不直接操作 widget。
主執行緒透過 `window.after(N, poll_fn)` 週期性讀取 Queue 並更新 UI。
CTk 的 `after()` 繼承自 tkinter，行為完全相同，現有模式無需修改。

## 測試策略

- 現有 `test_ui_ttkb.py` 作為功能對照參考
- 新增 `test_ui_ctk.py`，覆蓋相同的 smoke / unit 測試
- `--ui-smoke` 模式用於 CI 驗證視窗可正常建立並關閉
