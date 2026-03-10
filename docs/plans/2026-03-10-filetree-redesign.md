# FileTree Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace `ttk.Treeview` with a custom `CTkScrollableFrame`-based tree that uses emoji icons and supports modern per-row styling (hover, checked background).

**Architecture:** A `TreeNode` dataclass holds all state (no widgets). `_rebuild_visible()` computes the flat ordered list of visible nodes. `_sync_rows()` creates/updates `RowWidget` frames to match that list. All existing caller interfaces (`add_folder`, `add_file`, `toggle_check`, etc.) are preserved.

**Tech Stack:** Python 3.11+, customtkinter 5.x, tkinter, `dataclasses`

---

## Key files

- **Modify:** `ui_ctk.py` — all changes are here
- **Remove usage of:** `configure_treeview_style`, `treeview_tag_colors` from `ui_theme.py` (imports only; functions stay in ui_theme.py for now)
- **Test:** `test_ui_ttkb.py` (smoke tests exist; run after each task to ensure nothing broken)

## Baseline: run tests before starting

```bash
uv run pytest test_ui_ttkb.py test_ui_downloads.py -v 2>&1 | tail -20
```

---

### Task 1: Add `TreeNode` dataclass and data model state

**Goal:** Pure-Python data model for the tree. No widgets yet.

**Files:**
- Modify: `ui_ctk.py` — add dataclass near top (after imports, before `should_skip_file_row`)
- Modify: `ui_ctk.py:61-80` — add state fields to `__init__`

**Step 1: Add import and dataclass at top of file (after existing imports, before `should_skip_file_row` on line 30)**

```python
from dataclasses import dataclass, field

@dataclass
class TreeNode:
    node_id: str
    parent_id: str        # "" for root-level nodes
    name: str
    kind: str             # "folder" | "file"
    full_path: str        # "" for folders
    size: str
    file_type: str
    icon_group: str       # "folder"|"image"|"document"|"archive"|"code"|"audio"|"video"|"text"|"binary"
    checked: bool = False
    expanded: bool = False
    hidden: bool = False  # True when filtered out by search
    children: list = field(default_factory=list)  # ordered list of child node_ids
```

**Step 2: Add state fields to `__init__` (after `self.checkbox_checked = "✔ "` on line 70)**

```python
# FileTree data model
self.tree_nodes: dict[str, TreeNode] = {}
self.tree_roots: list[str] = []           # top-level node_ids in insertion order
self._node_counter: int = 0              # monotonic counter for unique node_ids
```

**Step 3: Write a quick manual verification**

```python
# In a scratch test (not committed): confirm dataclass works
node = TreeNode(node_id="n1", parent_id="", name="test", kind="folder",
                full_path="", size="", file_type="", icon_group="folder")
assert node.children == []
assert not node.checked
```

**Step 4: Commit**

```bash
git add ui_ctk.py
git commit -m "feat: add TreeNode dataclass and data model state"
```

---

### Task 2: Build `RowWidget` class

**Goal:** A single row frame with indent, chevron, emoji icon, name, size, and type badge. Handles hover highlighting and checked-state background.

**Files:**
- Modify: `ui_ctk.py` — add `RowWidget` class after `TreeNode` dataclass, before `should_skip_file_row`

**Step 1: Add the `RowWidget` class**

```python
_EMOJI_ICONS = {
    "folder":   "📁",
    "image":    "🖼️",
    "document": "📄",
    "archive":  "🗜️",
    "code":     "💻",
    "audio":    "🎵",
    "video":    "🎬",
    "text":     "📝",
    "binary":   "⚙️",
}

_BG_NORMAL  = ("gray95", "gray17")
_BG_HOVER   = ("#E2E8F0", "#2D3748")
_BG_CHECKED = ("#DBEAFE", "#1E3A5F")
_BG_CHECKED_HOVER = ("#BFDBFE", "#1E40AF")


class RowWidget:
    """One visible row in the FileTree."""

    INDENT_PX = 20
    ROW_HEIGHT = 34

    def __init__(self, parent, app, node: TreeNode, depth: int):
        self.app = app
        self.node_id = node.node_id
        self._checked = node.checked
        self._hovered = False

        self.frame = ctk.CTkFrame(parent, height=self.ROW_HEIGHT, corner_radius=4)
        self.frame.pack(fill="x", padx=4, pady=1)
        self.frame.pack_propagate(False)

        # Indent spacer
        if depth > 0:
            ctk.CTkFrame(
                self.frame, width=depth * self.INDENT_PX,
                fg_color="transparent", height=self.ROW_HEIGHT,
            ).pack(side="left")

        # Chevron (folders) or invisible spacer (files)
        if node.kind == "folder":
            self.chevron = ctk.CTkButton(
                self.frame, text="▶" if not node.expanded else "▼",
                width=22, height=22, fg_color="transparent",
                hover_color=("gray85", "gray30"), text_color=("gray40", "gray60"),
                font=ctk.CTkFont(size=10),
                command=lambda: app._on_chevron_click(self.node_id),
            )
            self.chevron.pack(side="left", padx=(2, 0))
        else:
            ctk.CTkFrame(
                self.frame, width=26, fg_color="transparent", height=self.ROW_HEIGHT,
            ).pack(side="left")

        # Emoji icon
        ctk.CTkLabel(
            self.frame,
            text=_EMOJI_ICONS.get(node.icon_group, "📄"),
            font=ctk.CTkFont(size=16),
            width=28,
        ).pack(side="left", padx=(2, 4))

        # Name label
        self.name_label = ctk.CTkLabel(
            self.frame,
            text=node.name,
            anchor="w",
            font=ctk.CTkFont(size=13, weight="bold" if node.kind == "folder" else "normal"),
        )
        self.name_label.pack(side="left", fill="x", expand=True)

        # Size + type (right side)
        if node.kind == "file":
            if node.size:
                ctk.CTkLabel(
                    self.frame,
                    text=node.size,
                    font=ctk.CTkFont(size=11),
                    text_color=("gray50", "gray60"),
                    width=80,
                    anchor="e",
                ).pack(side="right", padx=(0, 4))
            if node.icon_group and node.icon_group != "binary":
                ctk.CTkLabel(
                    self.frame,
                    text=node.icon_group,
                    font=ctk.CTkFont(size=10),
                    text_color=("gray50", "gray60"),
                    width=60,
                    anchor="e",
                ).pack(side="right", padx=(0, 2))

        self._update_bg()

        # Hover + click bindings on frame and all children
        self._bind_all(self.frame)

    def _bind_all(self, widget):
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)
        widget.bind("<Button-1>", self._on_click)
        for child in widget.winfo_children():
            self._bind_all(child)

    def _on_enter(self, _event=None):
        self._hovered = True
        self._update_bg()

    def _on_leave(self, _event=None):
        self._hovered = False
        self._update_bg()

    def _on_click(self, event):
        self.app._on_row_click(self.node_id, event)

    def set_checked(self, checked: bool):
        self._checked = checked
        self._update_bg()

    def set_chevron(self, expanded: bool):
        if hasattr(self, "chevron"):
            self.chevron.configure(text="▼" if expanded else "▶")

    def _update_bg(self):
        if self._checked and self._hovered:
            color = _BG_CHECKED_HOVER
        elif self._checked:
            color = _BG_CHECKED
        elif self._hovered:
            color = _BG_HOVER
        else:
            color = _BG_NORMAL
        self.frame.configure(fg_color=color)

    def destroy(self):
        self.frame.destroy()
```

**Step 2: Run smoke tests**

```bash
uv run pytest test_ui_ttkb.py -v -k "smoke" 2>&1 | tail -10
```

Expected: passes (RowWidget not yet wired up)

**Step 3: Commit**

```bash
git add ui_ctk.py
git commit -m "feat: add RowWidget class with emoji icons and hover/checked styling"
```

---

### Task 3: Build `_build_filetree()` to replace `_build_treeview()`

**Goal:** Replace the `ttk.Treeview` container with a `CTkScrollableFrame`. Wire up search bar. Store references needed by later tasks.

**Files:**
- Modify: `ui_ctk.py:393-455` — replace `_build_treeview` entirely
- Modify: `ui_ctk.py:136` — change `self._build_treeview()` to `self._build_filetree()`

**Step 1: Replace `_build_treeview` method (lines 393–455 inclusive)**

```python
def _build_filetree(self) -> None:
    outer = ctk.CTkFrame(self.window, fg_color="transparent")
    outer.grid(row=2, column=0, sticky="nsew", padx=10, pady=(4, 0))
    outer.grid_columnconfigure(0, weight=1)
    outer.grid_rowconfigure(1, weight=1)

    # Search bar
    search_bar = ctk.CTkFrame(outer, fg_color="transparent")
    search_bar.grid(row=0, column=0, sticky="ew", pady=(0, 4))
    search_bar.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(search_bar, text="Search").grid(row=0, column=0, padx=(0, 6))
    self.search_var = tk.StringVar()
    self.search_entry = ctk.CTkEntry(search_bar, textvariable=self.search_var)
    self.search_entry.grid(row=0, column=1, sticky="ew")
    self.search_var.trace_add("write", self.on_search_filter_changed)

    # Scrollable tree container
    self.tree_scroll_frame = ctk.CTkScrollableFrame(
        outer,
        fg_color=("gray95", "gray17"),
        corner_radius=8,
    )
    self.tree_scroll_frame.grid(row=1, column=0, sticky="nsew")

    # Runtime state for view layer
    self._visible_nodes: list[str] = []
    self._row_widgets: dict[str, RowWidget] = {}
```

**Step 2: Update `_build_full_ui` to call the new method (line 136)**

Change:
```python
        self._build_treeview()
```
To:
```python
        self._build_filetree()
```

**Step 3: Update `_build_full_ui` state init (line 141-145): remove `self.sort_reverse` etc. temporarily is OK; keep them to avoid AttributeErrors**

No change needed here — those lines stay.

**Step 4: Update `_build_ui_smoke_only` — add missing attributes that callers expect**

Find `_build_ui_smoke_only` (around line 121). After the existing lines add:

```python
        self.tree_nodes = {}
        self.tree_roots = []
        self._node_counter = 0
        self._visible_nodes = []
        self._row_widgets = {}
        self.tree_scroll_frame = None
        self.full_tree_backup = {}
        self.sort_reverse = False
        self.drag_anchor_item = ""
        self._last_toggle_time = 0.0
        self._search_after_id = None
        self.context_menu = tk.Menu(self.window, tearoff=0)
```

**Step 5: Remove old imports that are no longer needed**

In the `from ui_theme import (...)` block, remove:
- `configure_treeview_style`
- `treeview_tag_colors`

Also remove `ttk` from `from tkinter import filedialog, messagebox, ttk` → `from tkinter import filedialog, messagebox`

Wait — `ttk` is still used in `configure_action_button_styles` calls inside `_build_full_ui` (line 50). Leave `ttk` import for now; clean up in Task 8.

**Step 6: Run smoke tests**

```bash
uv run python index_ripper.py --ui-smoke 2>&1 | tail -5
uv run pytest test_ui_ttkb.py -v 2>&1 | tail -15
```

Expected: app launches without error; smoke tests pass.

**Step 7: Commit**

```bash
git add ui_ctk.py
git commit -m "feat: replace _build_treeview with _build_filetree (CTkScrollableFrame)"
```

---

### Task 4: Implement `_rebuild_visible()` and `_sync_rows()`

**Goal:** Core view logic. `_rebuild_visible()` does a DFS walk of `tree_nodes` respecting `expanded` and `hidden`. `_sync_rows()` creates new `RowWidget`s and removes stale ones.

**Files:**
- Modify: `ui_ctk.py` — add two methods after `_build_filetree`

**Step 1: Add `_rebuild_visible` and `_sync_rows` methods**

```python
def _rebuild_visible(self) -> None:
    """Recompute self._visible_nodes from data model (DFS, respects expanded/hidden)."""
    result: list[str] = []

    def _walk(node_id: str) -> None:
        node = self.tree_nodes.get(node_id)
        if node is None or node.hidden:
            return
        result.append(node_id)
        if node.kind == "folder" and node.expanded:
            for child_id in node.children:
                _walk(child_id)

    for root_id in self.tree_roots:
        _walk(root_id)

    self._visible_nodes = result

def _sync_rows(self) -> None:
    """Create/destroy RowWidgets to match _visible_nodes."""
    if self.tree_scroll_frame is None:
        return

    new_ids = set(self._visible_nodes)
    # Remove rows no longer visible
    for node_id in list(self._row_widgets):
        if node_id not in new_ids:
            self._row_widgets.pop(node_id).destroy()

    # Repack all rows in correct order
    for widget in self.tree_scroll_frame.winfo_children():
        widget.pack_forget()

    for node_id in self._visible_nodes:
        node = self.tree_nodes[node_id]
        depth = self._node_depth(node_id)
        if node_id not in self._row_widgets:
            self._row_widgets[node_id] = RowWidget(
                self.tree_scroll_frame, self, node, depth
            )
        else:
            self._row_widgets[node_id].frame.pack(fill="x", padx=4, pady=1)

def _node_depth(self, node_id: str) -> int:
    depth = 0
    node = self.tree_nodes.get(node_id)
    while node and node.parent_id:
        depth += 1
        node = self.tree_nodes.get(node.parent_id)
    return depth

def _next_node_id(self) -> str:
    self._node_counter += 1
    return f"n{self._node_counter}"
```

**Step 2: Add click handlers referenced by RowWidget**

```python
def _on_row_click(self, node_id: str, event=None) -> None:
    now = time.monotonic()
    if now - self._last_toggle_time < 0.25:
        return
    self._last_toggle_time = now
    node = self.tree_nodes.get(node_id)
    if node is None:
        return
    if node.kind == "folder":
        self._on_chevron_click(node_id)
    else:
        self.toggle_check(node_id)

def _on_chevron_click(self, node_id: str) -> None:
    node = self.tree_nodes.get(node_id)
    if node is None or node.kind != "folder":
        return
    node.expanded = not node.expanded
    row = self._row_widgets.get(node_id)
    if row:
        row.set_chevron(node.expanded)
    self._rebuild_visible()
    self._sync_rows()
```

**Step 3: Run smoke tests**

```bash
uv run pytest test_ui_ttkb.py -v 2>&1 | tail -15
```

**Step 4: Commit**

```bash
git add ui_ctk.py
git commit -m "feat: implement _rebuild_visible and _sync_rows for FileTree view layer"
```

---

### Task 5: Rewrite `add_folder()` and `add_file()`

**Goal:** Insert nodes into the data model (not Treeview), then call `_rebuild_visible` + `_sync_rows`.

**Files:**
- Modify: `ui_ctk.py:1092–1202` — replace both methods entirely

**Step 1: Replace `add_folder` (currently line 1092)**

```python
def add_folder(self, dir_path: str, url: str) -> str:
    """Ensure all path segments exist as folder nodes; return leaf node_id."""
    if not dir_path:
        dir_path = "/"
    parts = [p for p in dir_path.split("/") if p]

    parent_id = ""
    current_path = ""
    for part in parts:
        current_path = current_path + "/" + part
        with self.folders_dict_lock:
            existing_id = self.folders.get(current_path)
        if existing_id:
            parent_id = existing_id
            continue

        node_id = self._next_node_id()
        node = TreeNode(
            node_id=node_id,
            parent_id=parent_id,
            name=part,
            kind="folder",
            full_path="",
            size="",
            file_type="",
            icon_group="folder",
        )
        self.tree_nodes[node_id] = node
        if parent_id:
            self.tree_nodes[parent_id].children.append(node_id)
        else:
            self.tree_roots.append(node_id)

        with self.folders_dict_lock:
            self.folders[current_path] = node_id
        parent_id = node_id

    self._rebuild_visible()
    self._sync_rows()
    return parent_id
```

**Step 2: Replace `add_file` (currently line 1135)**

```python
def add_file(self, dir_path: str, url: str, file_name: str, size, file_type: str, full_path: str) -> None:
    """Add a file node to the tree."""
    if not file_name:
        return
    is_html_dir_like = (
        isinstance(file_type, str)
        and "text/html" in file_type.lower()
        and "." not in (file_name or "")
    )
    parent_id = self.add_folder(dir_path, url)

    with self.files_dict_lock:
        existing_entry = self.files_dict.get(full_path)
        if should_skip_file_row(existing_entry):
            return
        if is_html_dir_like:
            self.files_dict.pop(full_path, None)
        else:
            self.files_dict[full_path] = {
                "url": url,
                "file_name": file_name,
                "size": size,
                "file_type": file_type,
                "path": dir_path,
            }

    if is_html_dir_like:
        folder_path = f"{dir_path.rstrip('/')}/{file_name}".replace("//", "/")
        self.add_folder(folder_path, url)
        return

    ext = normalize_extension(file_name)
    self._add_file_type_filter(ext)
    self.file_type_counts[ext] = self.file_type_counts.get(ext, 0) + 1
    cb = self.file_type_widgets.get(ext)
    if cb:
        label = ext if ext else "(no ext)"
        cb.configure(text=f"{label} ({self.file_type_counts[ext]})")
    var = self.file_types.get(ext)
    if var is not None and not var.get():
        return

    group = self._file_icon_and_group(file_name, file_type)
    node_id = self._next_node_id()
    node = TreeNode(
        node_id=node_id,
        parent_id=parent_id,
        name=file_name,
        kind="file",
        full_path=full_path or "",
        size=size or "",
        file_type=file_type or "",
        icon_group=group,
        checked=full_path in self.checked_items,
    )
    self.tree_nodes[node_id] = node
    if parent_id:
        self.tree_nodes[parent_id].children.append(node_id)
    else:
        self.tree_roots.append(node_id)

    self._rebuild_visible()
    self._sync_rows()
```

**Note:** `_rebuild_visible` + `_sync_rows` is called once per file during scan. This is acceptable for ~1000 items (each call is O(visible_nodes)). If performance is sluggish, batch them by adding a `_pending_rebuild` flag and scheduling via `window.after(0, ...)`.

**Step 3: Run the app and do a real scan to verify folders and files appear**

```bash
uv run python index_ripper.py
```

Enter a URL, click Scan, verify file/folder rows appear in the tree.

**Step 4: Commit**

```bash
git add ui_ctk.py
git commit -m "feat: rewrite add_folder and add_file to use TreeNode data model"
```

---

### Task 6: Rewrite `toggle_check()`, `select_all()`, `deselect_all()`

**Goal:** Checkbox logic using data model. Update `RowWidget` background. Maintain `checked_items`.

**Files:**
- Modify: `ui_ctk.py:821–932` — replace `toggle_check`, `select_all`, `deselect_all`, and related methods

**Step 1: Replace `toggle_check` (currently line 821)**

```python
def toggle_check(self, node_id: str, force_check=None, _skip_children: bool = False) -> None:
    node = self.tree_nodes.get(node_id)
    if node is None:
        return
    new_checked = (not node.checked) if force_check is None else bool(force_check)
    node.checked = new_checked

    if node.kind == "file" and node.full_path:
        if new_checked:
            self.checked_items.add(node.full_path)
        else:
            self.checked_items.discard(node.full_path)

    row = self._row_widgets.get(node_id)
    if row:
        row.set_checked(new_checked)

    if node.kind == "folder" and not _skip_children:
        for child_id in node.children:
            self.toggle_check(child_id, force_check=new_checked)
```

**Step 2: Replace `select_all` and `deselect_all` (currently lines 926-932)**

```python
def select_all(self) -> None:
    for node_id in list(self.tree_nodes):
        self.toggle_check(node_id, force_check=True, _skip_children=True)

def deselect_all(self) -> None:
    for node_id in list(self.tree_nodes):
        self.toggle_check(node_id, force_check=False, _skip_children=True)
```

**Step 3: Replace `_all_tree_items` — keep for API compatibility but use tree_nodes**

```python
def _all_tree_items(self) -> list[str]:
    """Return all node_ids in DFS order."""
    out: list[str] = []
    def _walk(node_id: str) -> None:
        out.append(node_id)
        node = self.tree_nodes.get(node_id)
        if node:
            for child_id in node.children:
                _walk(child_id)
    for root_id in self.tree_roots:
        _walk(root_id)
    return out
```

**Step 4: Remove or stub old helper methods that referenced `self.tree` (ttk.Treeview)**

Remove these methods entirely (they're Treeview-specific and no longer needed):
- `_set_item_checked_visual`
- `_strip_checkmark`
- `_focused_tree_item`
- `on_tree_click` — replace with `_on_row_click` (already added in Task 4)
- `on_tree_drag_select`
- `on_tree_space`
- `on_tree_enter`
- `_on_tree_select_all`
- `show_context_menu` — keep but update to not use `self.tree.identify_row`

**Step 5: Update `show_context_menu`**

```python
def show_context_menu(self, event) -> None:
    try:
        self.context_menu.tk_popup(event.x_root, event.y_root)
    finally:
        self.context_menu.grab_release()
```

**Step 6: Commit**

```bash
git add ui_ctk.py
git commit -m "feat: rewrite toggle_check, select_all, deselect_all using TreeNode model"
```

---

### Task 7: Rewrite `expand_all`, `collapse_all`, `sort_tree`, and `_on_type_filter_changed`

**Goal:** These methods previously walked the Treeview; rewrite to use `tree_nodes`.

**Files:**
- Modify: `ui_ctk.py:934–961, 1486–1515`

**Step 1: Replace `expand_all` and `collapse_all`**

```python
def expand_all(self, parent: str = "") -> None:
    targets = self.tree_roots if not parent else self.tree_nodes[parent].children
    for node_id in targets:
        node = self.tree_nodes.get(node_id)
        if node and node.kind == "folder":
            node.expanded = True
            self.expand_all(node_id)
    self._rebuild_visible()
    self._sync_rows()

def collapse_all(self, parent: str = "") -> None:
    targets = self.tree_roots if not parent else self.tree_nodes[parent].children
    for node_id in targets:
        node = self.tree_nodes.get(node_id)
        if node and node.kind == "folder":
            node.expanded = False
            self.collapse_all(node_id)
    self._rebuild_visible()
    self._sync_rows()
```

**Step 2: Replace `sort_tree`**

```python
def sort_tree(self, col: str = "name") -> None:
    def sort_children(children: list[str]) -> None:
        if not children:
            return
        def key(node_id: str) -> str:
            node = self.tree_nodes.get(node_id)
            if node is None:
                return ""
            if col == "size":
                return node.size.lower()
            if col == "type":
                return node.icon_group.lower()
            return node.name.lower()
        children.sort(key=key, reverse=self.sort_reverse)
        for node_id in children:
            node = self.tree_nodes.get(node_id)
            if node:
                sort_children(node.children)

    sort_children(self.tree_roots)
    self.sort_reverse = not self.sort_reverse
    self._rebuild_visible()
    self._sync_rows()
```

**Step 3: Replace `_on_type_filter_changed`**

```python
def _on_type_filter_changed(self, ext: str) -> None:
    if self.full_tree_backup:
        return  # search filter active; handled by _filter_tree_by_term
    var = self.file_types.get(ext)
    if var is None:
        return
    visible = var.get()
    for node in self.tree_nodes.values():
        if node.kind == "file" and normalize_extension(node.name) == ext:
            node.hidden = not visible
    self._rebuild_visible()
    self._sync_rows()
```

**Step 4: Commit**

```bash
git add ui_ctk.py
git commit -m "feat: rewrite expand_all, collapse_all, sort_tree, type filter using TreeNode"
```

---

### Task 8: Rewrite `_backup_full_tree`, `_restore_full_tree`, `_filter_tree_by_term`

**Goal:** Search filter backup/restore using data model instead of Treeview state.

**Files:**
- Modify: `ui_ctk.py:1373–1448`

**Step 1: Replace `_backup_full_tree`**

```python
def _backup_full_tree(self) -> None:
    """Snapshot tree_nodes and tree_roots for search filter restore."""
    import copy
    self.full_tree_backup = {
        "nodes": copy.deepcopy(self.tree_nodes),
        "roots": list(self.tree_roots),
        "folders": dict(self.folders),
    }
```

**Step 2: Replace `_restore_full_tree`**

```python
def _restore_full_tree(self) -> None:
    """Restore tree_nodes from backup (undo search filter)."""
    if not self.full_tree_backup:
        return
    self.tree_nodes = self.full_tree_backup["nodes"]
    self.tree_roots = self.full_tree_backup["roots"]
    with self.folders_dict_lock:
        self.folders = self.full_tree_backup["folders"]
    self.full_tree_backup = {}

    # Destroy all existing row widgets and rebuild
    for row in self._row_widgets.values():
        row.destroy()
    self._row_widgets.clear()
    self._rebuild_visible()
    self._sync_rows()
```

**Step 3: Replace `_filter_tree_by_term`**

```python
def _filter_tree_by_term(self, term: str) -> None:
    """Mark nodes hidden if they (and their descendants) don't match term."""
    term = term.lower()

    def matches(node_id: str) -> bool:
        node = self.tree_nodes.get(node_id)
        if node is None:
            return False
        if term in node.name.lower() or term in node.full_path.lower():
            return True
        return any(matches(child_id) for child_id in node.children)

    def apply_visibility(node_id: str) -> None:
        node = self.tree_nodes.get(node_id)
        if node is None:
            return
        if matches(node_id):
            node.hidden = False
            node.expanded = True  # auto-expand matching folders
        else:
            node.hidden = True
        for child_id in node.children:
            apply_visibility(child_id)

    for root_id in self.tree_roots:
        apply_visibility(root_id)

    self._rebuild_visible()
    self._sync_rows()
```

**Step 4: Commit**

```bash
git add ui_ctk.py
git commit -m "feat: rewrite backup/restore/filter using TreeNode model"
```

---

### Task 9: Rewrite `clear_scan_results` and remove all remaining `self.tree` (Treeview) references

**Goal:** Final cleanup. Replace every `self.tree.*` call with tree_nodes model. Remove unused imports.

**Files:**
- Modify: `ui_ctk.py:1040–1062` — `clear_scan_results`
- Modify: `ui_ctk.py` — remove `self.checkbox_checked`, remove `ttk`/`configure_treeview_style`/`treeview_tag_colors` imports

**Step 1: Replace `clear_scan_results`**

```python
def clear_scan_results(self) -> None:
    if self.is_scanning:
        return
    self._drain_queues()

    # Clear data model
    self.tree_nodes.clear()
    self.tree_roots.clear()
    self._node_counter = 0
    with self.folders_dict_lock:
        self.folders.clear()

    # Destroy row widgets
    for row in self._row_widgets.values():
        row.destroy()
    self._row_widgets.clear()
    self._visible_nodes.clear()

    # Clear other state
    with self.files_dict_lock:
        self.files_dict.clear()
    if hasattr(self, "filters_container"):
        for widget in self.filters_container.winfo_children():
            widget.destroy()
    self.file_types.clear()
    self.file_type_counts.clear()
    self.file_type_widgets.clear()
    self.checked_items.clear()
    self.full_tree_backup.clear() if isinstance(self.full_tree_backup, dict) else None
    self.full_tree_backup = {}
    self.scanned_urls = 0
    self.total_urls = 0
    self.progress_bar.set(0)
    self.progress_label.configure(text="")
    self._set_status("Ready", "#059669")
```

**Step 2: Search for remaining `self.tree` references**

```bash
grep -n "self\.tree\b" ui_ctk.py | grep -v "tree_nodes\|tree_roots\|tree_scroll\|_tree_icons\|file_tree\|tree_backup\|_node_counter\|_visible\|_row_widget"
```

Expected: only innocuous hits like `self.tree_roots` etc. Fix any remaining `self.tree.xxx` (Treeview) calls.

**Step 3: Remove unused imports**

- Remove `ttk` from `from tkinter import filedialog, messagebox, ttk` if no ttk usage remains
- Remove `configure_treeview_style`, `treeview_tag_colors` from `ui_theme` import
- Remove `_init_tree_icons` method (entire method, no longer needed)
- Remove `self.checkbox_checked = "✔ "` from `__init__`

**Step 4: Run full test suite**

```bash
uv run pytest test_ui_ttkb.py test_ui_downloads.py test_ui_theme.py -v 2>&1 | tail -20
```

**Step 5: Launch the app and do an end-to-end test**

```bash
uv run python index_ripper.py
```

Test checklist:
- [ ] App launches without errors
- [ ] Scan a URL → files appear with emoji icons
- [ ] Click a file → row turns blue (checked)
- [ ] Click a folder → expands/collapses
- [ ] Type in search → non-matching rows disappear
- [ ] Clear search → rows reappear
- [ ] Select All / Deselect All works
- [ ] Expand All / Collapse All works
- [ ] File type checkboxes show/hide rows

**Step 6: Commit**

```bash
git add ui_ctk.py
git commit -m "feat: complete FileTree migration - remove all ttk.Treeview references"
```

---

## Done

All 9 tasks complete. The `ttk.Treeview` is fully replaced with a `CTkScrollableFrame`-based custom tree using emoji icons, hover effects, and checked-state background highlighting.
