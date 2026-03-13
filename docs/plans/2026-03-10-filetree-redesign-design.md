# FileTree Redesign — Design Document

**Date:** 2026-03-10
**Status:** Approved

## Goal

Replace `ttk.Treeview` with a custom `FileTree` component built on `CTkScrollableFrame` + emoji icons, delivering a modern UI while preserving all existing functional interfaces.

## Problem

`ttk.Treeview` forces icons to be `tk.PhotoImage` pixel art (limited quality) and prevents per-row custom styling (hover, checked background, badges). The current pixel-art icons look like plain colored blocks.

## Design

### Architecture — three layers

**1. Data model (pure Python, no widgets)**

```python
@dataclass
class TreeNode:
    node_id: str
    parent_id: str       # "" for root
    name: str
    kind: str            # "folder" | "file"
    full_path: str       # "" for folders
    size: str
    file_type: str
    icon_group: str      # "folder" | "image" | "document" | ...
    checked: bool
    expanded: bool
    children: list[str]  # ordered child node_ids
```

```python
# Stored on WebsiteCopierCtk:
self.tree_nodes: dict[str, TreeNode]
self.tree_roots: list[str]           # top-level node_ids in order
```

**2. View layer (CTkScrollableFrame)**

- Container: `ctk.CTkScrollableFrame` replaces `ttk.Treeview`
- `_visible_nodes: list[str]` — flat ordered list of currently visible nodes
- `_row_widgets: dict[str, RowWidget]` — node_id → row frame (created lazily)
- `_rebuild_visible()` — recomputes `_visible_nodes` from data model (expand/collapse, filter)
- `_sync_rows()` — creates/removes row widgets to match `_visible_nodes`

**3. Row widget (RowWidget)**

Each row is a `ctk.CTkFrame` containing:
```
[indent spacer] [▶/▼ or spacer] [emoji label] [name label]  [size label] [type badge]
```
- `indent` = `depth * 20` px spacer
- Expand/collapse button: 16×16 `ctk.CTkButton` with `▶`/`▼` text, no border
- Emoji icon: `ctk.CTkLabel` 22px font
- Name: `ctk.CTkLabel`, bold for folders
- Size/type: right-aligned small labels

### Visual spec

| State | Background |
|---|---|
| Normal | transparent (inherits CTkScrollableFrame) |
| Hover | `("#E2E8F0", "#2D3748")` |
| Checked | `("#DBEAFE", "#1E3A5F")` |
| Checked + Hover | `("#BFDBFE", "#1E40AF")` |

Row height: 34px (via `height` on inner frame)
Font: SF Pro Text 13 (name), 11 (size/type)

### Emoji icon mapping

| group | emoji |
|---|---|
| folder | 📁 |
| image | 🖼️ |
| document | 📄 |
| archive | 🗜️ |
| code | 💻 |
| audio | 🎵 |
| video | 🎬 |
| text | 📝 |
| binary | ⚙️ |

### Preserved public interfaces (no changes to callers)

- `add_folder(dir_path, url) → str`
- `add_file(dir_path, url, file_name, size, file_type, full_path)`
- `toggle_check(item_id, force_check=None, _skip_children=False)`
- `select_all() / deselect_all()`
- `expand_all() / collapse_all()`
- `_backup_full_tree() / _restore_full_tree()`
- `_filter_tree_by_term(term)`
- `sort_tree(col)`
- `checked_items: set[str]` — still maintained

### Implementation notes

- `add_folder` / `add_file` still called from main thread (via `_poll_scan_queue`)
- `_rebuild_visible()` is O(n); call only on expand/collapse/filter, not per row
- `_sync_rows()` uses `grid()` / `grid_forget()` for show/hide (no widget destruction)
- Search filter: set `node.hidden = True` on non-matching nodes; `_rebuild_visible` skips them
- Backup/restore: serialise/deserialise `tree_nodes` + `tree_roots` dicts
- `checked_items` set is the source of truth for download; unchanged
