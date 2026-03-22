# UI/UX Redesign — Design Document

**Date:** 2026-03-10
**Status:** Approved

## Goal

Simplify and clean up the IndexRipper UI to match a macOS-native single-window app aesthetic. The primary workflow is linear: enter URL → scan → select files → download.

## Layout Overview

```
┌─────────────────────────────────────────────────────────┐
│  Row 0  Toolbar: URL + Scan + Status                    │
├─────────────────────────────────────────────────────────┤
│  Row 1  Search + Types filter                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Row 2  FileTree  (weight=1, fills remaining space)     │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  Row 3  Progress bar + Bottom control bar               │
├─────────────────────────────────────────────────────────┤
│  Row 4  Logs / Downloads panel (collapsible, default    │
│         hidden)                                         │
└─────────────────────────────────────────────────────────┘
```

Window: `1100×800`, minsize `800×550`. `grid_rowconfigure(2, weight=1)`.

---

## Row 0 — Toolbar

```
[URL_________________________________] [Scan] ● Ready
```

- `CTkEntry` for URL, `fill="x"`, height 36px, `column=0 weight=1`
- **Scan button**: text toggles `"Scan"` ↔ `"Stop Scan"` (single button, no separate Stop)
- **Pause Scan button**: hidden by default (`grid_remove`); shown only while scanning; toggles `"Pause Scan"` ↔ `"Resume Scan"`
- **Status indicator**: small colored dot (6×6 `CTkFrame`, `corner_radius=3`) + text label, right-aligned
  - Ready → green `#059669`
  - Scanning → amber `#B45309`
  - Stopped / Error → red `#B91C1C`
- **Remove Clear button**: scanning automatically clears previous results (`clear_scan_results()` called at scan start)

---

## Row 1 — Search + Types

```
🔍 [Search____________] │ □ mp4 (12)  □ zip (3)  □ jpg (8)  ↔
```

- Left: `CTkEntry` with 🔍 prefix label, fixed width 260px, `height=34`
- Vertical separator: 1px `CTkFrame(width=1, fg_color=("gray80","gray30"))`
- Right: `CTkScrollableFrame(orientation="horizontal", height=38)` — same as current `filters_container`, `fill="x" expand=True`
- **Remove "Types:" label** and **"✓ All / ✗ All" buttons** from Row 1
- Replace with right-click context menu on `filters_container`:
  - `Select All Types`
  - `Deselect All Types`
- Row total height: ~42px

---

## Row 2 — FileTree

```
📁 videos/                                           ▶
    🎬 movie.mp4                          1.2 GB
    🎬 trailer.mp4                        240 MB
📁 docs/                                             ▶
    📄 readme.txt                           4 KB
```

Changes from current implementation:

| Property | Before | After |
|----------|--------|-------|
| Chevron position | left of name | right edge of row |
| Checked style | blue background fill | 3px blue left border accent |
| Row height | 38px | 36px |
| Row gap (pady) | 1px | 0px |
| Type badge | shown right (e.g. "video") | **removed** |
| Size column | right-aligned, width=90 | right-aligned, width=80 |
| Empty state | blank | "Scanning…" during scan; "No files found" after |

### Checked accent border implementation

`RowWidget` uses a narrow `CTkFrame(width=3)` as the leftmost child, colored:
- unchecked: `fg_color="transparent"`
- checked: `fg_color=("#2563EB","#3B82F6")`

Background colors (hover/checked) remain but become more subtle:

| State | Light | Dark |
|-------|-------|------|
| Normal | transparent | transparent |
| Hover | `#F1F5F9` | `#1E293B` |
| Checked | `#EFF6FF` | `#172554` |
| Checked+Hover | `#DBEAFE` | `#1E3A5F` |

### Chevron on right

`RowWidget` packs chevron with `side="right"` before other right-side widgets, so it appears at the far right.

---

## Row 3 — Progress + Control bar

### Progress bar (Row 3a)

```
████████████░░░░░░  68%  Scanning… 34/50
```

- `CTkProgressBar(height=8, corner_radius=4)` — slimmer than current 14px
- Progress text on **same row** to the right of bar: `CTkLabel`, `anchor="w"`, auto-hide when text is empty
- When idle: progress bar hidden entirely (`grid_remove`); shown when scanning or downloading

### Control bar (Row 3b)

```
[Select All] [Deselect All]          [⬇ Download] [⏸ Pause] [📁 Folder] Threads [5▾]  [Logs ▾]
```

- Left group: `Select All` / `Deselect All` (secondary style, height=30)
- Right group (right-aligned):
  - `⬇ Download Selected` — primary blue button
  - `⏸ Pause` — secondary, `state="disabled"` until download starts
  - `📁 Folder` — secondary
  - `Threads` label + `CTkOptionMenu` (1–10, width=65)
  - `Logs ▾` toggle button — expands/collapses Row 4 panel

---

## Row 4 — Logs / Downloads panel

- **Default state: hidden** (`grid_remove` on startup)
- Fixed height: 160px
- `CTkTabview` with tabs: `Downloads` | `Logs`
- Default active tab: `Logs`
- Toggle button text: `"Logs ▾"` (collapsed) ↔ `"Logs ▴"` (expanded)

---

## Preserved public interfaces (no changes to callers)

All existing methods remain:
- `add_folder`, `add_file`, `toggle_check`, `select_all`, `deselect_all`
- `expand_all`, `collapse_all`, `sort_tree`
- `_backup_full_tree`, `_restore_full_tree`, `_filter_tree_by_term`
- `on_scan_started`, `on_scan_progress`, `on_scan_finished`
- `update_progress`, `update_download_status`
- `checked_items: set[str]`

---

## Implementation notes

- `_build_header()` → rename to `_build_toolbar()`, restructure columns
- `_build_filters_row()` → split into `_build_search_types_row()`; remove "Types:" label and All/None buttons; add context menu binding
- `_build_filetree()` → update `RowWidget` (chevron right, accent border, no type badge, smaller row)
- `_build_progress_section()` + `_build_download_controls()` → merge into `_build_bottom_bar()`
- `_build_panels()` → update default to hidden; update toggle button label
- `_build_full_ui()` → update `grid_rowconfigure`, call renamed builders
- `clear_scan_results()` → call automatically from `start_scan()` before starting thread
