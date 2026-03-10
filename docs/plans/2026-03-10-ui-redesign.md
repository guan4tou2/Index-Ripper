# UI/UX Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign IndexRipper's layout to a clean macOS-native style — slim toolbar, merged search+types row, dominant FileTree, slim bottom bar with collapsible panel.

**Architecture:** All changes are confined to `ui_ctk.py`. No new files. Five builder methods are renamed/rewritten; `RowWidget` gets cosmetic updates. All public interfaces and backend hooks are preserved unchanged.

**Tech Stack:** Python 3.11+, CustomTkinter (ctk), tkinter (tk/ttk)

**Design reference:** `docs/plans/2026-03-10-ui-redesign-design.md`

---

### Task 1: Update RowWidget — accent border, chevron right, remove type badge

**Files:**
- Modify: `ui_ctk.py:57-186` (module-level constants + RowWidget class)

**Context:**
`RowWidget` is the class that renders one visible row in the FileTree. Currently:
- Chevron (`▶`/`▼`) is on the **left** side
- Checked state = blue full-row background fill
- Type badge is shown on the right (`node.icon_group` text)
- `ROW_HEIGHT = 38`, `pady=1` in `pack()`

After this task:
- Chevron moves to **right** side
- Checked state = transparent/subtle background + **3px blue left accent bar**
- Type badge **removed**
- `ROW_HEIGHT = 36`, `pady=0`

**Step 1: Update module-level color constants**

Replace lines 57-60 in `ui_ctk.py`:

```python
_BG_NORMAL        = "transparent"
_BG_HOVER         = ("#F1F5F9", "#1E293B")
_BG_CHECKED       = ("#EFF6FF", "#172554")
_BG_CHECKED_HOVER = ("#DBEAFE", "#1E3A5F")
```

**Step 2: Update `RowWidget.__init__` — ROW_HEIGHT, pady, accent bar, chevron right, no type badge**

Replace the entire `RowWidget` class body (lines ~63-186) with:

```python
class RowWidget:
    """One visible row in the FileTree."""

    INDENT_PX = 20
    ROW_HEIGHT = 36

    def __init__(self, parent, app, node: TreeNode, depth: int):
        self.app = app
        self.node_id = node.node_id
        self._checked = node.checked
        self._hovered = False

        self.frame = ctk.CTkFrame(parent, height=self.ROW_HEIGHT, corner_radius=4)
        self.frame.pack(fill="x", padx=4, pady=0)
        self.frame.pack_propagate(False)

        # 3-px accent bar (left edge, blue when checked)
        self._accent = ctk.CTkFrame(
            self.frame, width=3, corner_radius=0,
            fg_color="#2563EB" if node.checked else "transparent",
        )
        self._accent.pack(side="left", fill="y")

        # Indent spacer
        if depth > 0:
            ctk.CTkFrame(
                self.frame, width=depth * self.INDENT_PX,
                fg_color="transparent", height=self.ROW_HEIGHT,
            ).pack(side="left")

        # Emoji icon
        ctk.CTkLabel(
            self.frame,
            text=_EMOJI_ICONS.get(node.icon_group, "📄"),
            font=ctk.CTkFont(size=18),
            width=28,
        ).pack(side="left", padx=(4, 4))

        # Name label
        self.name_label = ctk.CTkLabel(
            self.frame,
            text=node.name,
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold" if node.kind == "folder" else "normal"),
        )
        self.name_label.pack(side="left", fill="x", expand=True)

        # Chevron on RIGHT (folders only)
        if node.kind == "folder":
            self.chevron = ctk.CTkButton(
                self.frame, text="▼" if node.expanded else "▶",
                width=22, height=22, fg_color="transparent",
                hover_color=("gray85", "gray30"), text_color=("gray40", "gray60"),
                font=ctk.CTkFont(size=10),
                command=lambda: app._on_chevron_click(self.node_id),
            )
            self.chevron.pack(side="right", padx=(4, 4))
        elif node.kind == "file" and node.size:
            # Size label (right side, files only)
            ctk.CTkLabel(
                self.frame,
                text=node.size,
                font=ctk.CTkFont(size=12),
                text_color=("gray50", "gray60"),
                width=80,
                anchor="e",
            ).pack(side="right", padx=(0, 8))

        self._bind_all(self.frame)

    def _bind_all(self, widget) -> None:
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)
        widget.bind("<Button-1>", self._on_click)
        for child in widget.winfo_children():
            self._bind_all(child)

    def _on_enter(self, _event=None) -> None:
        self._hovered = True
        self._update_bg()

    def _on_leave(self, _event=None) -> None:
        self._hovered = False
        self._update_bg()

    def _on_click(self, event) -> None:
        self.app._on_row_click(self.node_id, event)

    def set_checked(self, checked: bool) -> None:
        self._checked = checked
        self._accent.configure(
            fg_color="#2563EB" if checked else "transparent"
        )
        self._update_bg()

    def set_chevron(self, expanded: bool) -> None:
        if hasattr(self, "chevron"):
            self.chevron.configure(text="▼" if expanded else "▶")

    def _update_bg(self) -> None:
        if self._checked and self._hovered:
            color = _BG_CHECKED_HOVER
        elif self._checked:
            color = _BG_CHECKED
        elif self._hovered:
            color = _BG_HOVER
        else:
            color = _BG_NORMAL
        self.frame.configure(fg_color=color)

    def destroy(self) -> None:
        self.frame.destroy()
```

**Step 3: Verify smoke test still passes**

```bash
uv run python index_ripper.py --ui-smoke
```

Expected: exits with code 0, no exception.

**Step 4: Run unit tests**

```bash
uv run python -m pytest test_ui_theme.py test_ui_downloads.py test_backend.py -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add ui_ctk.py
git commit -m "feat: RowWidget — accent border, chevron right, remove type badge"
```

---

### Task 2: Rewrite `_build_header` → `_build_toolbar`

**Files:**
- Modify: `ui_ctk.py` — method `_build_header` (~line 350)

**Context:**
Current `_build_header`:
- Row layout: `URL label` | `URL entry` | `Status label` | `[Scan] [Pause Scan] [Clear]`
- Status is a plain text label; Pause Scan is always visible; Clear is a separate button

After this task:
- Status = colored 6px dot + text (right-aligned)
- Pause Scan = hidden by default (`grid_remove`), shown only during scan
- Clear button = **removed** (auto-clear happens in `start_scan`)
- Method renamed to `_build_toolbar`

**Step 1: Replace `_build_header` with `_build_toolbar`**

Replace the entire `_build_header` method with:

```python
def _build_toolbar(self) -> None:
    toolbar = ctk.CTkFrame(self.window, fg_color="transparent")
    toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
    toolbar.grid_columnconfigure(1, weight=1)

    self.url_var = tk.StringVar()
    self.url_entry = ctk.CTkEntry(
        toolbar, textvariable=self.url_var,
        placeholder_text="https://",
        font=ctk.CTkFont(size=14),
        height=36,
    )
    self.url_entry.grid(row=0, column=0, sticky="ew", columnspan=2, padx=(0, 8))
    toolbar.grid_columnconfigure(0, weight=0)
    toolbar.grid_columnconfigure(1, weight=1)

    # Re-do: URL takes column 0 with weight=1; buttons on right
    # Use a simpler single-row approach:
    toolbar.grid_columnconfigure(0, weight=1)
    toolbar.grid_columnconfigure(1, weight=0)
    toolbar.grid_columnconfigure(2, weight=0)

    self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

    # Scan button (toggles Scan ↔ Stop Scan)
    self.scan_btn = ctk.CTkButton(toolbar, text="Scan", command=self.start_scan, width=90)
    self.scan_btn.grid(row=0, column=1, padx=(0, 4))

    # Pause Scan button — hidden by default, shown only while scanning
    self.scan_pause_btn = ctk.CTkButton(
        toolbar, text="Pause",
        fg_color=("gray70", "gray30"),
        hover_color=("gray60", "gray40"),
        command=self.toggle_scan_pause,
        width=80,
        state="disabled",
    )
    self.scan_pause_btn.grid(row=0, column=2, padx=(0, 8))
    self.scan_pause_btn.grid_remove()   # hidden until scan starts

    # Status: dot + text in a small frame
    status_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
    status_frame.grid(row=0, column=3, sticky="e")

    self._status_dot = ctk.CTkFrame(
        status_frame, width=8, height=8, corner_radius=4,
        fg_color="#059669",
    )
    self._status_dot.pack(side="left", padx=(0, 5))

    self.status_label = ctk.CTkLabel(
        status_frame, text="Ready",
        text_color="#059669", font=ctk.CTkFont(size=13),
    )
    self.status_label.pack(side="left")

    # URL context menu (right-click paste)
    self.url_context_menu = tk.Menu(self.window, tearoff=0)
    self.url_context_menu.add_command(label="Paste", command=self._paste_into_url_entry)
    self.url_entry.bind("<Button-2>", self._show_url_context_menu)
    self.url_entry.bind("<Button-3>", self._show_url_context_menu)
```

**Step 2: Update `_set_status` to also configure the dot color**

Replace the `_set_status` method:

```python
def _set_status(self, text: str, color: str = "#059669") -> None:
    try:
        self.status_label.configure(text=text, text_color=color)
        self._status_dot.configure(fg_color=color)
    except Exception:
        pass
```

**Step 3: Update `on_scan_started` — show Pause Scan button**

In `on_scan_started`:
```python
def on_scan_started(self, *, url: str = "") -> None:
    self.scan_btn.configure(text="Stop Scan")
    self.scan_pause_btn.grid()          # show
    self.scan_pause_btn.configure(state="normal")
    self.progress_bar.set(0)
    self.progress_label.configure(text="Scanning…")
    self._set_status("Scanning", "#B45309")
```

**Step 4: Update `on_scan_finished` — hide Pause Scan button**

In `on_scan_finished` inside `_finish()`:
```python
self.scan_btn.configure(text="Scan")
self.scan_pause_btn.grid_remove()       # hide
self.scan_pause_btn.configure(text="Pause", state="disabled")
```

**Step 5: Update `_build_full_ui` to call `_build_toolbar` instead of `_build_header`**

In `_build_full_ui`, replace the call `self._build_header()` with `self._build_toolbar()`.

**Step 6: Smoke test + unit tests**

```bash
uv run python index_ripper.py --ui-smoke
uv run python -m pytest test_backend.py test_ui_theme.py -v
```

Expected: all pass.

**Step 7: Commit**

```bash
git add ui_ctk.py
git commit -m "feat: toolbar redesign — status dot, hide pause btn, remove clear btn"
```

---

### Task 3: Rewrite `_build_filters_row` → `_build_search_types_row`

**Files:**
- Modify: `ui_ctk.py` — method `_build_filters_row` (~line 556)

**Context:**
Current `_build_filters_row` builds **two rows**:
- Row 1 (ctrl_row_frame): placeholder, later filled by `_build_download_controls`
- Row 2 (types_row): "Types:" label + `[✓ All]` `[✗ All]` + horizontal scrollable checkboxes

After this task: **single row** combining Search + Types:
- Left: 🔍 + Search entry (fixed width 260px)
- Separator (1px vertical line)
- Right: horizontal scrollable checkboxes (no label, no ✓/✗ All buttons)
- Right-click on checkboxes area: context menu with "Select All Types" / "Deselect All Types"

The `_ctrl_row_frame` is still created (Task 4 uses it for download controls).

**Step 1: Replace `_build_filters_row`**

```python
def _build_search_types_row(self) -> None:
    # ── Row 1: download controls placeholder (filled in _build_bottom_bar) ──
    self._ctrl_row_frame = ctk.CTkFrame(self.window, fg_color="transparent")
    self._ctrl_row_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(6, 0))
    self._ctrl_row_frame.grid_columnconfigure(0, weight=1)

    # ── Row 2: Search + separator + Types ────────────────────────────────
    row = ctk.CTkFrame(self.window, fg_color="transparent")
    row.grid(row=2, column=0, sticky="ew", padx=10, pady=(6, 0))
    row.grid_columnconfigure(2, weight=1)

    # Search icon + entry
    ctk.CTkLabel(row, text="🔍", font=ctk.CTkFont(size=15)).grid(
        row=0, column=0, padx=(0, 4)
    )
    self.search_var = tk.StringVar()
    self.search_entry = ctk.CTkEntry(
        row, textvariable=self.search_var,
        placeholder_text="Search files…",
        width=260, height=34,
    )
    self.search_entry.grid(row=0, column=1, padx=(0, 8))
    self.search_var.trace_add("write", self.on_search_filter_changed)

    # Vertical separator
    ctk.CTkFrame(row, width=1, height=30, fg_color=("gray80", "gray30")).grid(
        row=0, column=2, sticky="ns", padx=(0, 8)
    )
    row.grid_columnconfigure(2, weight=0)
    row.grid_columnconfigure(3, weight=1)

    # Horizontal scrollable types
    self.filters_container = ctk.CTkScrollableFrame(
        row,
        height=38,
        orientation="horizontal",
        fg_color="transparent",
    )
    self.filters_container.grid(row=0, column=3, sticky="ew")
    self._bind_hscroll_wheel(self.filters_container)

    # Right-click context menu on types container
    self._types_context_menu = tk.Menu(self.window, tearoff=0)
    self._types_context_menu.add_command(
        label="Select All Types", command=self.select_all_types
    )
    self._types_context_menu.add_command(
        label="Deselect All Types", command=self.deselect_all_types
    )
    self.filters_container.bind("<Button-2>", self._show_types_context_menu)
    self.filters_container.bind("<Button-3>", self._show_types_context_menu)
```

**Step 2: Add `_show_types_context_menu` helper**

```python
def _show_types_context_menu(self, event) -> None:
    try:
        self._types_context_menu.tk_popup(event.x_root, event.y_root)
    finally:
        self._types_context_menu.grab_release()
```

**Step 3: Update `_build_full_ui` to call `_build_search_types_row` instead of `_build_filters_row`**

Replace `self._build_filters_row()` with `self._build_search_types_row()`.

Also update `grid_rowconfigure` in `_build_full_ui` — the filetree is now at **row 3** (search+types moved from row 2 to row 2, filetree stays at row 3):

```python
def _build_full_ui(self) -> None:
    self.window.grid_columnconfigure(0, weight=1)
    self.window.grid_rowconfigure(3, weight=1)   # filetree
    self.window.grid_rowconfigure(5, weight=0)   # panels

    self._build_toolbar()              # row 0
    self._build_search_types_row()     # rows 1 (ctrl placeholder) + 2 (search+types)
    self._build_filetree()             # row 3
    self._build_bottom_bar()           # rows 4 (progress) + …
    self._build_panels()               # row 5
    # _build_download_controls() content is now in _build_bottom_bar()

    self.sort_reverse = False
    self.full_tree_backup = {}

    self.context_menu = tk.Menu(self.window, tearoff=0)
    self.context_menu.add_command(label="Select All", command=self.select_all)
    self.context_menu.add_command(label="Deselect All", command=self.deselect_all)
    self.context_menu.add_separator()
    self.context_menu.add_command(label="Expand All", command=self.expand_all)
    self.context_menu.add_command(label="Collapse All", command=self.collapse_all)
```

**Step 4: Smoke test**

```bash
uv run python index_ripper.py --ui-smoke
```

Expected: exits 0.

**Step 5: Commit**

```bash
git add ui_ctk.py
git commit -m "feat: merge search + types into single row, add types context menu"
```

---

### Task 4: Rewrite progress + controls → `_build_bottom_bar`

**Files:**
- Modify: `ui_ctk.py` — methods `_build_progress_section`, `_build_download_controls`, `_build_full_ui`

**Context:**
Currently:
- `_build_progress_section` (row 4): progress bar (height=14) + label on separate line
- `_build_download_controls` (appended into `_ctrl_row_frame` row 1): Select All, Deselect All, Download, Pause, Folder, Threads, Hide Panels

After this task:
- **Row 4a** (progress row): slim bar (height=8) + text on same line; hidden when idle
- **Row 4b** (control bar): Select All, Deselect All | Download, Pause, Folder, Threads | **Logs ▾** toggle
- `_build_download_controls` is **removed** (absorbed into `_build_bottom_bar`)
- `_build_progress_section` is **removed** (absorbed into `_build_bottom_bar`)

**Step 1: Add `_build_bottom_bar` method**

```python
def _build_bottom_bar(self) -> None:
    _s = dict(
        fg_color=("gray80", "gray25"),
        text_color=("gray10", "gray90"),
        hover_color=("gray70", "gray35"),
        height=30,
        font=ctk.CTkFont(size=12),
    )

    # ── Row 4: progress bar + text ─────────────────────────────────────
    progress_frame = ctk.CTkFrame(self.window, fg_color="transparent")
    progress_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=(4, 0))
    progress_frame.grid_columnconfigure(0, weight=1)
    progress_frame.grid_remove()   # hidden until scanning/downloading
    self._progress_frame = progress_frame

    self.progress_bar = ctk.CTkProgressBar(
        progress_frame, height=8, corner_radius=4
    )
    self.progress_bar.set(0)
    self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 8))

    self.progress_label = ctk.CTkLabel(
        progress_frame, text="",
        font=ctk.CTkFont(size=12),
        anchor="w", width=220,
    )
    self.progress_label.grid(row=0, column=1, sticky="w")

    # ── Row 5: control bar ─────────────────────────────────────────────
    ctrl = ctk.CTkFrame(self.window, fg_color="transparent")
    ctrl.grid(row=5, column=0, sticky="ew", padx=10, pady=(4, 6))
    ctrl.grid_columnconfigure(1, weight=1)  # elastic gap between left and right

    # Left: select controls
    left = ctk.CTkFrame(ctrl, fg_color="transparent")
    left.grid(row=0, column=0, sticky="w")
    ctk.CTkButton(left, text="Select All",   command=self.select_all,   width=100, **_s).pack(side="left", padx=(0, 4))
    ctk.CTkButton(left, text="Deselect All", command=self.deselect_all, width=110, **_s).pack(side="left")

    # Right: download controls + logs toggle
    right = ctk.CTkFrame(ctrl, fg_color="transparent")
    right.grid(row=0, column=2, sticky="e")

    self.download_btn = ctk.CTkButton(
        right, text="⬇ Download", command=self.download_selected, height=30,
    )
    self.download_btn.pack(side="left", padx=(0, 4))

    self.pause_btn = ctk.CTkButton(
        right, text="⏸ Pause",
        fg_color=("gray70", "gray30"),
        hover_color=("gray60", "gray40"),
        command=self.toggle_pause,
        state="disabled", height=30,
    )
    self.pause_btn.pack(side="left", padx=(0, 4))

    self.path_btn = ctk.CTkButton(
        right, text="📁 Folder",
        fg_color=("gray70", "gray30"),
        hover_color=("gray60", "gray40"),
        command=self.choose_download_path, height=30,
    )
    self.path_btn.pack(side="left", padx=(0, 8))

    ctk.CTkLabel(right, text="Threads", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))

    self.threads_var = tk.StringVar(value="5")
    self.threads_combo = ctk.CTkOptionMenu(
        right,
        values=[str(i) for i in range(1, 11)],
        variable=self.threads_var,
        command=self.update_thread_count,
        width=65, height=30,
    )
    self.threads_combo.pack(side="left", padx=(0, 12))

    self.panels_visible = False
    self.toggle_panels_btn = ctk.CTkButton(
        right, text="Logs ▾",
        command=self.toggle_panels,
        width=80, **_s,
    )
    self.toggle_panels_btn.pack(side="left")
```

**Step 2: Update `toggle_panels` for new button text and row index**

```python
def toggle_panels(self) -> None:
    if self.panels_visible:
        if hasattr(self, "_panels_widget"):
            self._panels_widget.grid_remove()
        self.panels_visible = False
        self.toggle_panels_btn.configure(text="Logs ▾")
    else:
        if hasattr(self, "_panels_widget"):
            self._panels_widget.grid()
        self.panels_visible = True
        self.toggle_panels_btn.configure(text="Logs ▴")
```

**Step 3: Update progress visibility**

Add a helper to show/hide the progress row:

```python
def _show_progress(self, visible: bool) -> None:
    try:
        if visible:
            self._progress_frame.grid()
        else:
            self._progress_frame.grid_remove()
    except Exception:
        pass
```

Update `on_scan_started`:
```python
def on_scan_started(self, *, url: str = "") -> None:
    self.scan_btn.configure(text="Stop Scan")
    self.scan_pause_btn.grid()
    self.scan_pause_btn.configure(state="normal")
    self.progress_bar.set(0)
    self.progress_label.configure(text="Scanning…")
    self._show_progress(True)
    self._set_status("Scanning", "#B45309")
```

Update `on_scan_finished` `_finish()`:
```python
self.scan_btn.configure(text="Scan")
self.scan_pause_btn.grid_remove()
self.scan_pause_btn.configure(text="Pause", state="disabled")
if stopped:
    self.progress_bar.set(0)
    self.progress_label.configure(text="Scan stopped")
    self._set_status("Stopped", "#B91C1C")
    self._show_progress(False)
else:
    self.progress_bar.set(1)
    n = len(self.files_dict)
    self.progress_label.configure(text=f"Done — {n} files found")
    self._set_status("Ready", "#059669")
    # keep progress bar visible to show "done" state; hide after 3 s
    self.window.after(3000, lambda: self._show_progress(False))
```

**Step 4: Remove `_build_download_controls` and `_build_progress_section`**

Delete both methods entirely from `ui_ctk.py`.

**Step 5: Update `_build_full_ui` grid rows**

```python
def _build_full_ui(self) -> None:
    self.window.grid_columnconfigure(0, weight=1)
    self.window.grid_rowconfigure(3, weight=1)   # filetree

    self._build_toolbar()             # row 0
    self._build_search_types_row()    # row 1 (ctrl placeholder) + row 2 (search+types)
    self._build_filetree()            # row 3
    self._build_bottom_bar()          # row 4 (progress) + row 5 (controls)
    self._build_panels()              # row 6

    self.sort_reverse = False
    self.full_tree_backup = {}

    self.context_menu = tk.Menu(self.window, tearoff=0)
    self.context_menu.add_command(label="Select All", command=self.select_all)
    self.context_menu.add_command(label="Deselect All", command=self.deselect_all)
    self.context_menu.add_separator()
    self.context_menu.add_command(label="Expand All", command=self.expand_all)
    self.context_menu.add_command(label="Collapse All", command=self.collapse_all)
```

**Step 6: Smoke test**

```bash
uv run python index_ripper.py --ui-smoke
uv run python -m pytest test_backend.py test_ui_theme.py test_ui_downloads.py -v
```

Expected: exits 0 / all pass.

**Step 7: Commit**

```bash
git add ui_ctk.py
git commit -m "feat: merge progress + controls into _build_bottom_bar; panels default hidden"
```

---

### Task 5: Update `_build_panels` and `_build_filetree` — row index + empty state

**Files:**
- Modify: `ui_ctk.py` — methods `_build_panels`, `_build_filetree`

**Context:**
After Task 4, the panels tab is at **row 6** (not row 5). Also:
- Panels default to **hidden** (already set in `_build_bottom_bar`)
- FileTree should show an empty-state label when no nodes exist

**Step 1: Update `_build_panels` row index**

```python
def _build_panels(self) -> None:
    self.panels_notebook = ctk.CTkTabview(self.window, height=160)
    self.panels_notebook.grid(row=6, column=0, sticky="ew", padx=10, pady=(0, 10))
    self._panels_widget = self.panels_notebook

    downloads_tab = self.panels_notebook.add("Downloads")
    logs_tab = self.panels_notebook.add("Logs")
    self.panels_notebook.set("Logs")

    downloads_scroll = ctk.CTkScrollableFrame(downloads_tab, height=100)
    downloads_scroll.pack(fill="both", expand=True)
    self.downloads_panel = DownloadsPanel(
        parent_frame=downloads_scroll,
        ctk=ctk,
        tk=tk,
        tokens=self.ui_tokens,
    )

    self.log_text = ctk.CTkTextbox(logs_tab, height=100, wrap="word")
    self.log_text.pack(fill="both", expand=True)

    # Start hidden (toggle via Logs ▾ button)
    self.panels_notebook.grid_remove()
```

**Step 2: Add empty-state label to `_build_filetree`**

In `_build_filetree`, after creating `tree_scroll_frame`, add:

```python
# Empty state label (shown when no nodes; hidden when rows exist)
self._empty_label = ctk.CTkLabel(
    self.tree_scroll_frame,
    text="Enter a URL above and click Scan",
    text_color=("gray50", "gray60"),
    font=ctk.CTkFont(size=14),
)
self._empty_label.pack(expand=True)
```

**Step 3: Update `_sync_rows` to show/hide empty label**

At the end of `_sync_rows`:

```python
# Show empty state if no visible rows
if hasattr(self, "_empty_label"):
    if self._visible_nodes:
        self._empty_label.pack_forget()
    else:
        self._empty_label.pack(expand=True)
```

**Step 4: Update empty label text during scanning**

In `on_scan_started`:
```python
if hasattr(self, "_empty_label"):
    self._empty_label.configure(text="Scanning…")
```

In `on_scan_finished` inside `_finish()`:
```python
if hasattr(self, "_empty_label") and not self.tree_nodes:
    self._empty_label.configure(
        text="No files found" if not stopped else "Enter a URL above and click Scan"
    )
```

**Step 5: Smoke test**

```bash
uv run python index_ripper.py --ui-smoke
uv run python -m pytest -v
```

Expected: all pass.

**Step 6: Commit**

```bash
git add ui_ctk.py
git commit -m "feat: panels at row 6, default hidden; filetree empty state label"
```

---

### Task 6: Auto-clear on scan start + window size + final wiring

**Files:**
- Modify: `ui_ctk.py` — `__init__`, `start_scan`, `_build_ui_smoke_only`

**Context:**
- `start_scan` should call `clear_scan_results()` automatically (removing need for a Clear button)
- Window default size changed to `1100×800`, minsize `800×550`
- `_build_ui_smoke_only` must initialise `_progress_frame` stub to avoid AttributeError
- `_ctrl_row_frame` in `_build_full_ui` is no longer filled by `_build_download_controls` — it was the Row 1 placeholder used by the old control flow. It's now empty and can be removed entirely. Check if anything still references it.

**Step 1: Update window geometry in `__init__`**

```python
self.window.geometry("1100x800")
self.window.minsize(800, 550)
```

**Step 2: Update `start_scan` to auto-clear**

```python
def start_scan(self) -> None:
    url = self.url_var.get().strip()
    if self.is_scanning:
        self.backend.should_stop = True
        self._set_status("Stopping", "#B45309")
        return
    if not url:
        self.notify_error("Error", "Please enter a URL")
        return

    # Auto-clear previous results before starting
    self.clear_scan_results()

    self.backend.should_stop = False
    try:
        self.download_path = default_download_folder(url, os.getcwd())
    except Exception:
        self.download_path = os.path.join(os.getcwd(), "downloads")

    t = threading.Thread(target=self.backend.scan_website, args=(url,), daemon=True)
    t.start()
```

**Step 3: Update `clear_scan_results` to also reset progress and empty label**

Add at end of `clear_scan_results`:
```python
self._show_progress(False)
if hasattr(self, "_empty_label"):
    self._empty_label.configure(text="Enter a URL above and click Scan")
    self._empty_label.pack(expand=True)
```

**Step 4: Remove `_ctrl_row_frame` (Row 1 placeholder) from `_build_search_types_row`**

Check: `_ctrl_row_frame` is no longer referenced by any method after removing `_build_download_controls`. Remove these lines from `_build_search_types_row`:

```python
# DELETE these lines:
self._ctrl_row_frame = ctk.CTkFrame(self.window, fg_color="transparent")
self._ctrl_row_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(6, 0))
self._ctrl_row_frame.grid_columnconfigure(0, weight=1)
```

And update `_build_full_ui` grid: rows are now `0=toolbar`, `1=search+types`, `2=filetree`, `3=progress`, `4=controls`, `5=panels`:

```python
def _build_full_ui(self) -> None:
    self.window.grid_columnconfigure(0, weight=1)
    self.window.grid_rowconfigure(2, weight=1)   # filetree at row 2

    self._build_toolbar()             # row 0
    self._build_search_types_row()    # row 1
    self._build_filetree()            # row 2
    self._build_bottom_bar()          # row 3 (progress) + row 4 (controls)
    self._build_panels()              # row 5

    self.sort_reverse = False
    self.full_tree_backup = {}

    self.context_menu = tk.Menu(self.window, tearoff=0)
    self.context_menu.add_command(label="Select All", command=self.select_all)
    self.context_menu.add_command(label="Deselect All", command=self.deselect_all)
    self.context_menu.add_separator()
    self.context_menu.add_command(label="Expand All", command=self.expand_all)
    self.context_menu.add_command(label="Collapse All", command=self.collapse_all)
```

Update `_build_search_types_row` to use **row=1** for the search+types row (not row 2):

```python
row.grid(row=1, column=0, sticky="ew", padx=10, pady=(6, 0))
```

Update `_build_filetree` to use **row=2**:
```python
outer.grid(row=2, column=0, sticky="nsew", padx=10, pady=(4, 0))
```

Update `_build_bottom_bar` rows: progress=**3**, controls=**4**:
```python
progress_frame.grid(row=3, ...)
ctrl.grid(row=4, ...)
```

Update `_build_panels` to use **row=5**:
```python
self.panels_notebook.grid(row=5, ...)
```

**Step 5: Fix `_build_ui_smoke_only` stubs**

Add `_progress_frame`, `_status_dot`, `_empty_label` stubs:

```python
def _build_ui_smoke_only(self) -> None:
    self.url_var = tk.StringVar(value="https://example.com/")
    self.search_var = tk.StringVar()
    self.log_text = ctk.CTkTextbox(self.window, height=80)
    self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
    self.log_text.insert("end", "UI smoke minimal view initialized.\n")
    self.panels_notebook = None
    self.logs_tab = None
    self._visible_nodes = []
    self._row_widgets = {}
    self.tree_scroll_frame = None
    self.full_tree_backup = {}
    self.sort_reverse = False
    self._last_toggle_time = 0.0
    self._search_after_id = None
    self.tree_nodes = {}
    self.tree_roots = []
    self._node_counter = 0
    self.context_menu = tk.Menu(self.window, tearoff=0)
    # Stubs for attributes used by hooks
    self._progress_frame = None
    self._status_dot = None
    self._empty_label = None
    self.progress_bar = type("_Stub", (), {"set": lambda s, v: None, "grid": lambda s, **kw: None, "grid_remove": lambda s: None})()
    self.progress_label = type("_Stub", (), {"configure": lambda s, **kw: None})()
    self.status_label = type("_Stub", (), {"configure": lambda s, **kw: None})()
    self.scan_btn = type("_Stub", (), {"configure": lambda s, **kw: None})()
    self.scan_pause_btn = type("_Stub", (), {"configure": lambda s, **kw: None, "grid": lambda s: None, "grid_remove": lambda s: None})()
```

**Step 6: Run full test suite + smoke test**

```bash
uv run python index_ripper.py --ui-smoke
uv run python -m pytest -v
```

Expected: smoke exits 0, all pytest tests pass.

**Step 7: Commit**

```bash
git add ui_ctk.py
git commit -m "feat: auto-clear on scan, final row wiring, window 1100x800"
```

---

## Final verification

After all tasks complete, run:

```bash
# Smoke test
uv run python index_ripper.py --ui-smoke

# Full test suite
uv run python -m pytest -v

# Self test (no real network)
uv run python index_ripper.py --self-test
```

All three should succeed with no errors.
