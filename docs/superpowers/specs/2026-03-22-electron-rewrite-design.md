# Index Ripper Electron Rewrite — Design Spec

## Goal

Rewrite Index Ripper from Python + CustomTkinter to Electron + React + TypeScript + Node.js. This is a full rewrite — no Python code is retained. The new app delivers all existing features (website scanning, file tree browsing, filtering, multi-threaded download with pause/resume/cancel) plus a new multi-site task queue feature, wrapped in a modern split-panel UI built with shadcn/ui.

## Architecture

### Process Model

**Main Process (Node.js):**
- Scanner service — two-phase: first recursively discover all URLs, then issue HEAD requests per file for metadata (size, MIME type). Scan concurrency: 10 parallel workers.
- Download manager — concurrent streaming downloads with progress tracking, automatic retry (3 attempts with exponential backoff for 5xx errors)
- Task queue — manages multiple scan/download jobs across different sites, each task is independent
- File system — safe path construction, settings persistence

**Renderer Process (React + TypeScript):**
- Single-window app with split-panel layout, native title bar (not frameless — avoids cross-platform drag/resize issues)
- Communicates with main process exclusively via typed IPC channels
- No direct file system or network access

**Preload Script:**
- Exposes a typed `window.api` object via `contextBridge`
- All IPC channels explicitly whitelisted — no `remote` module usage

### IPC Channel Design

All task-scoped channels include `taskId` as the first parameter.

```
renderer → main:
  scan:start(taskId, url)           → begins recursive crawl
  scan:stop(taskId)                 → aborts in-progress scan
  scan:pause(taskId) / scan:resume(taskId)
  download:start(taskId, files[], destPath)
  download:pause(taskId) / download:resume(taskId)
  download:cancel(taskId, fileId)
  download:cancelAll(taskId)        → cancel all active downloads
  download:retry(taskId, fileId)    → retry a failed download
  download:setWorkers(count)        → change concurrency (1-10)
  task:create(url)                  → add new site to task queue
  task:remove(taskId)
  settings:get() / settings:set(data)
  dialog:selectFolder()             → open native folder picker

main → renderer:
  scan:item(taskId, node)           → discovered file or directory
  scan:progress(taskId, scanned, total)
  scan:finished(taskId, stopped)
  scan:error(taskId, message)       → structured scan error
  download:progress(taskId, fileId, percent, speed)
  download:status(taskId, fileId, status)
  download:finished(taskId, completed, total)
  log:message(taskId, text)
```

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Framework | Electron 35+ | Desktop app with full OS integration |
| Build tool | electron-vite | Vite-based, fast HMR, TypeScript native |
| Frontend | React 19 + TypeScript | Complex state (tree, downloads, tasks) |
| Styling | Tailwind CSS v4 + shadcn/ui | Modern component library, dark mode built-in |
| State | Zustand | Lightweight, works well with React, no boilerplate |
| HTTP client | Electron `net` module | Respects system proxy, native to Electron |
| HTML parser | cheerio | jQuery-like API for parsing directory listings |
| Concurrency | p-queue | Configurable concurrent download/scan limit |
| Settings | electron-store | JSON persistence with schema validation |
| Tree virtualization | @tanstack/react-virtual | Better variable-height support than react-window |
| Packaging | electron-builder | Cross-platform builds (Windows, macOS, Linux) |

## UI Design

### Layout: Split Panel with Native Title Bar

```
┌─────────────────────────────────────────────────┐
│ Index Ripper                            — □ ×   │  ← native title bar
├─────────────────────────────────────────────────┤
│ [example.com] [mirror.site] [+]     (task tabs) │
├─────────────────────────────────────────────────┤
│ [https://example.com/files/  ] [Scan] [⬇] ● OK │
├────────────────────┬────────────────────────────┤
│ 🔍 Search...       │ [Downloads] [Logs]         │
│ .pdf(5) .jpg(12)   │                            │
│────────────────────│ ┌────────────────────────┐ │
│ 📁 documents    ▼  │ │ report.pdf    ✓ Done   │ │
│   ▌📄 report.pdf   │ │ ████████████████ 100%  │ │
│    📄 readme.txt   │ ├────────────────────────┤ │
│ 📁 images       ▶  │ │ photo.jpg    67% 1.2MB │ │
│ 📁 archives     ▶  │ │ ████████░░░░░░░  67%   │ │
│                    │ ├────────────────────────┤ │
│                    │ │ backup.zip    Queued    │ │
│                    │ │ ░░░░░░░░░░░░░░░   0%   │ │
│ 20 files, 3 dirs   │                            │
│ 2 selected         │ 1/3 done — ~2 min left     │
└────────────────────┴────────────────────────────┘
```

### Component Hierarchy

```
App
├── TaskTabs (multi-site tab bar with + button)
├── Toolbar (URL input, Scan button, Download button, thread count, status)
└── SplitPanel (resizable left/right)
    ├── LeftPanel
    │   ├── SearchBar (text filter input)
    │   ├── TypeFilters (scrollable checkbox chips)
    │   ├── FileTree (virtual-scrolled tree with checkboxes)
    │   └── StatusBar (file/folder count, selected count)
    └── RightPanel
        ├── TabSwitcher (Downloads / Logs toggle)
        ├── DownloadsList (per-file progress cards with cancel/retry)
        └── OverallProgress (aggregate progress bar + ETA)
```

### File Tree

- **Virtual scrolling** via `@tanstack/react-virtual` — flattened list approach, handles 10,000+ nodes
- Each row: accent bar (blue when checked) + icon + name + size + chevron
- Icons: same emoji set as current (📁📄🖼️🗜️💻🎵🎬📝⚙️)
- Checkbox toggling: click row to toggle, folders cascade to children
- Right-click context menu: Select All, Deselect All, Expand All, Collapse All
- Keyboard: Ctrl/Cmd+A select all, Ctrl/Cmd+F focus search, Ctrl/Cmd+L focus logs, Escape clear search
- macOS: standard edit shortcuts (Cmd+V/C/X/Z) work natively in text inputs (Electron handles this with native title bar)

### Notifications

- Toast notifications (shadcn/ui `Sonner`) for: scan complete, no files found, download complete, network errors
- Log panel for detailed messages

### Theme

- Dark mode only initially (matching current app aesthetic)
- Slate color palette from Tailwind (gray-900 backgrounds, blue-500 accents)
- shadcn/ui dark theme defaults for all interactive components

## Features

### Existing Features (preserved)

1. **Website scanning** — two-phase: recursive URL discovery (10 concurrent), then HEAD requests for file metadata (size, MIME type). Supports pause/resume/stop
2. **File tree** — hierarchical display with expand/collapse, checkbox selection, cascade
3. **File type filtering** — dynamic checkbox chips with counts, select/deselect all
4. **Search filtering** — real-time text search across file names and paths
5. **Configurable concurrent downloads** — 1-10 workers, adjustable at runtime via toolbar dropdown
6. **Per-file progress** — individual progress bars, speed display, status labels, cancel buttons
7. **Pause/resume downloads** — global pause affects all active downloads
8. **Directory structure preservation** — downloads mirror source hierarchy
9. **Partial file cleanup** — removes incomplete files on cancel/error
10. **Settings persistence** — remembers window size, panel proportions, thread count, last download path
11. **Automatic retry** — 3 retries with exponential backoff for transient HTTP errors (5xx)
12. **Default download folder** — auto-derived from site hostname (e.g., `~/Downloads/example.com/`)
13. **URL right-click context menu** — paste support in URL input

### New Feature: Multi-Site Task Queue

Each "task" represents one website scan/download session. Users can:
- Add new tasks via the `+` tab button (enters URL, starts scan)
- Switch between tasks — each task has its own file tree, download state, and progress
- Remove completed/cancelled tasks
- Tasks run independently — scanning site A while downloading from site B

Task lifecycle (state machine):
```
idle → scanning → scanned → downloading → done
                    ↓            ↓
                  error        error

Any state → cancelled (via task removal)
Scanning can be paused/resumed independently of downloads.
A single task cannot scan and download simultaneously.
```

Tasks are **not persisted** across app restarts. Closing the app discards all tasks.

## Data Models

All types live in `src/shared/types.ts` — imported by both main and renderer.

### TreeNode

```typescript
interface TreeNode {
  id: string
  parentId: string          // "" for roots
  name: string
  kind: 'folder' | 'file'
  url: string               // download URL (files only, "" for folders)
  fullPath: string          // relative path (e.g., "docs/sub" for folders, "docs/sub/file.txt" for files)
  size: string              // "245 KB" or "Unknown"
  fileType: string          // MIME type from Content-Type header
  iconGroup: string         // folder|image|document|archive|code|audio|video|text|binary
  checked: boolean
  expanded: boolean
  hidden: boolean           // filtered out by search/type
  children: string[]        // child node IDs
}
```

### Task

```typescript
interface Task {
  id: string
  url: string
  status: 'idle' | 'scanning' | 'scanned' | 'downloading' | 'done' | 'error' | 'cancelled'
  nodes: Record<string, TreeNode>    // id → TreeNode (flat map for O(1) lookup)
  roots: string[]                    // top-level node IDs in insertion order
  checkedFiles: string[]             // fullPath[] of checked files (serializable, derived from nodes)
  downloads: Record<string, DownloadItem>  // fileId → DownloadItem
  scanProgress: { scanned: number; total: number }
  downloadPath: string               // per-task download destination
}
```

`checkedFiles` is derived from `nodes` (all file nodes where `checked === true`). It exists as a convenience for `download:start` IPC calls. The source of truth for checked state is `TreeNode.checked`.

### DownloadItem

```typescript
interface DownloadItem {
  id: string                // same as TreeNode.id for correlation
  fileName: string
  url: string
  destPath: string
  status: 'queued' | 'downloading' | 'paused' | 'completed' | 'failed' | 'cancelled'
  progress: number          // 0-100
  speed: number             // bytes/sec
  totalSize: number
  downloadedSize: number
}
```

`DownloadItem.id` equals the corresponding `TreeNode.id`, enabling direct correlation between tree selection and download progress.

### Icon Mapping

MIME type to `iconGroup` mapping (in `src/shared/icons.ts`):

```typescript
function getIconGroup(fileName: string, mimeType: string): string {
  const ext = extname(fileName).toLowerCase()
  if (['.jpg','.jpeg','.png','.gif','.webp','.svg','.bmp','.ico'].includes(ext)) return 'image'
  if (['.md','.txt','.pdf','.doc','.docx','.rtf'].includes(ext)) return 'document'
  if (['.zip','.rar','.7z','.tar','.gz','.bz2','.xz'].includes(ext)) return 'archive'
  if (['.py','.js','.ts','.tsx','.jsx','.go','.rs','.java','.c','.cpp','.h','.json','.yaml','.yml','.toml','.xml','.html','.css','.sh'].includes(ext)) return 'code'
  if (mimeType.includes('audio/')) return 'audio'
  if (mimeType.includes('video/')) return 'video'
  if (mimeType.includes('text/')) return 'text'
  if (mimeType.includes('image/')) return 'image'
  return 'binary'
}
```

## Project Structure

```
electron-app/
├── package.json
├── electron.vite.config.ts
├── tsconfig.json
├── src/
│   ├── shared/
│   │   ├── types.ts                  # TreeNode, Task, DownloadItem interfaces
│   │   └── icons.ts                  # Icon/emoji mapping
│   ├── main/                         # Electron main process
│   │   ├── index.ts                  # App entry, window creation
│   │   ├── ipc.ts                    # IPC handler registration
│   │   ├── scanner.ts                # Two-phase website scanning
│   │   ├── downloader.ts            # Download manager with retry
│   │   ├── task-queue.ts            # Multi-site task management
│   │   └── utils.ts                 # Path sanitization, URL validation
│   ├── preload/
│   │   └── index.ts                 # contextBridge API exposure
│   └── renderer/                    # React app
│       ├── index.html
│       ├── main.tsx                 # React entry
│       ├── App.tsx                  # Root layout
│       ├── stores/
│       │   ├── task-store.ts        # Zustand: tasks, active task, settings
│       │   ├── tree-store.ts        # Zustand: file tree state per task
│       │   └── download-store.ts    # Zustand: download state per task
│       ├── components/
│       │   ├── TaskTabs.tsx
│       │   ├── Toolbar.tsx
│       │   ├── SplitPanel.tsx
│       │   ├── SearchBar.tsx
│       │   ├── TypeFilters.tsx
│       │   ├── FileTree.tsx         # Virtual-scrolled tree
│       │   ├── FileTreeRow.tsx      # Single row component
│       │   ├── DownloadsList.tsx
│       │   ├── DownloadCard.tsx
│       │   ├── LogsPanel.tsx
│       │   └── StatusBar.tsx
│       └── hooks/
│           ├── useIpc.ts           # IPC event subscription hook
│           └── useFileTree.ts      # Tree traversal/filtering logic
├── resources/                       # App icons
│   ├── icon.ico
│   └── icon.png
└── electron-builder.yml             # Packaging config
```

## Error Handling

- **Network errors during scan**: Log to UI via `log:message`, report via `scan:error`, skip failed URLs, continue scanning
- **Download failures**: Mark as "Failed", automatic retry (3 attempts, exponential backoff for 5xx). Manual retry via `download:retry` after max retries exhausted
- **Invalid URLs**: Validate before scan, show inline error on URL input
- **Path traversal**: Sanitize all path segments — strip `..`, `/`, `\`, Windows-illegal chars
- **Scope validation**: Ensure discovered URLs stay within base domain/path (same origin + path prefix check)

## Testing Strategy

- **Main process unit tests**: Scanner parsing, URL validation, path sanitization, icon mapping (Vitest)
- **Renderer component tests**: React Testing Library for FileTree, DownloadCard, TypeFilters
- **IPC integration tests**: Verify channel contracts between main and renderer
- **E2E consideration**: Playwright + Electron support for full-flow testing (future)

## Migration Notes

- This is a **new project** in an `electron-app/` directory alongside the existing `src/` Python code
- The Python code remains untouched — users can choose which version to use
- Feature parity is the primary goal; the Electron version should do everything the Python version does
- The multi-site task queue is the only net-new feature
