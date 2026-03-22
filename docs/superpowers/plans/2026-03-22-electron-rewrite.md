# Index Ripper Electron Rewrite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new Electron desktop app (React + TypeScript + Node.js) that replaces the Python version with full feature parity plus multi-site task queue support.

**Architecture:** Electron main process handles scanning and downloads (cheerio + Electron net + p-queue). React renderer with Zustand stores displays a split-panel UI. IPC bridge connects them via typed channels. All shared types in `src/shared/`.

**Tech Stack:** Electron 35+, electron-vite, React 19, TypeScript, Tailwind CSS v4, shadcn/ui, Zustand, cheerio, p-queue, @tanstack/react-virtual, electron-store, electron-builder

**Spec:** `docs/superpowers/specs/2026-03-22-electron-rewrite-design.md`

---

## Task 1: Project Scaffolding

**Files:**
- Create: `electron-app/package.json`
- Create: `electron-app/electron.vite.config.ts`
- Create: `electron-app/tsconfig.json`
- Create: `electron-app/tsconfig.node.json`
- Create: `electron-app/tsconfig.web.json`
- Create: `electron-app/src/main/index.ts`
- Create: `electron-app/src/preload/index.ts`
- Create: `electron-app/src/renderer/index.html`
- Create: `electron-app/src/renderer/main.tsx`
- Create: `electron-app/src/renderer/App.tsx`
- Create: `electron-app/electron-builder.yml`
- Create: `electron-app/resources/icon.png`

- [ ] **Step 1: Scaffold project with electron-vite**

```bash
cd /Users/guantou/Desktop/Index-Ripper
npm create @quick-start/electron@latest electron-app -- --template react-ts
```

If the interactive scaffolding fails, create manually. The result should be a working electron-vite project with React + TypeScript.

- [ ] **Step 2: Install core dependencies**

```bash
cd /Users/guantou/Desktop/Index-Ripper/electron-app
npm install zustand cheerio p-queue electron-store
npm install -D tailwindcss @tailwindcss/vite @tanstack/react-virtual vitest
```

- [ ] **Step 3: Configure Tailwind CSS v4**

In `electron-app/src/renderer/main.css`:
```css
@import "tailwindcss";
```

In `electron-app/electron.vite.config.ts`, add Tailwind plugin to renderer config:
```typescript
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  // ...
  renderer: {
    plugins: [react(), tailwindcss()],
  },
})
```

- [ ] **Step 4: Set up shadcn/ui**

```bash
cd /Users/guantou/Desktop/Index-Ripper/electron-app
npx shadcn@latest init
```

Configure with: TypeScript, New York style, Slate base color, CSS variables.

Add commonly needed components:
```bash
npx shadcn@latest add button tabs checkbox scroll-area context-menu progress sonner
```

- [ ] **Step 5: Create minimal App.tsx**

```tsx
export default function App(): React.ReactElement {
  return (
    <div className="h-screen bg-slate-950 text-slate-100 flex items-center justify-center">
      <h1 className="text-2xl font-bold">Index Ripper</h1>
    </div>
  )
}
```

- [ ] **Step 6: Verify app launches**

```bash
cd /Users/guantou/Desktop/Index-Ripper/electron-app
npm run dev
```

Expected: Electron window opens showing "Index Ripper" text on dark background.

- [ ] **Step 7: Copy app icon**

```bash
cp /Users/guantou/Desktop/Index-Ripper/app.png /Users/guantou/Desktop/Index-Ripper/electron-app/resources/icon.png
```

- [ ] **Step 8: Commit**

```bash
cd /Users/guantou/Desktop/Index-Ripper
git add electron-app/
git commit -m "feat(electron): scaffold project with electron-vite, React, TypeScript, Tailwind, shadcn/ui"
```

---

## Task 2: Shared Types & Utilities

**Files:**
- Create: `electron-app/src/shared/types.ts`
- Create: `electron-app/src/shared/icons.ts`
- Create: `electron-app/src/main/utils.ts`
- Test: `electron-app/src/main/__tests__/utils.test.ts`

- [ ] **Step 1: Create shared types**

```typescript
// electron-app/src/shared/types.ts

export interface TreeNode {
  id: string
  parentId: string
  name: string
  kind: 'folder' | 'file'
  url: string
  fullPath: string
  size: string
  fileType: string
  iconGroup: string
  checked: boolean
  expanded: boolean
  hidden: boolean
  children: string[]
}

export interface Task {
  id: string
  url: string
  status: 'idle' | 'scanning' | 'scanned' | 'downloading' | 'done' | 'error' | 'cancelled'
  nodes: Record<string, TreeNode>
  roots: string[]
  checkedFiles: string[]
  downloads: Record<string, DownloadItem>
  scanProgress: { scanned: number; total: number }
  downloadPath: string
}

export interface DownloadItem {
  id: string
  fileName: string
  url: string
  destPath: string
  status: 'queued' | 'downloading' | 'paused' | 'completed' | 'failed' | 'cancelled'
  progress: number
  speed: number
  totalSize: number
  downloadedSize: number
}

export type ScanStatus = Task['status']
export type DownloadStatus = DownloadItem['status']
```

- [ ] **Step 2: Create icon mapping**

```typescript
// electron-app/src/shared/icons.ts
import { extname } from 'path'

const IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.ico']
const DOC_EXTS = ['.md', '.txt', '.pdf', '.doc', '.docx', '.rtf']
const ARCHIVE_EXTS = ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz']
const CODE_EXTS = [
  '.py', '.js', '.ts', '.tsx', '.jsx', '.go', '.rs', '.java', '.c', '.cpp',
  '.h', '.hpp', '.json', '.yaml', '.yml', '.toml', '.xml', '.html', '.css', '.sh',
]

export function getIconGroup(fileName: string, mimeType: string): string {
  const ext = extname(fileName).toLowerCase()
  if (IMAGE_EXTS.includes(ext)) return 'image'
  if (DOC_EXTS.includes(ext)) return 'document'
  if (ARCHIVE_EXTS.includes(ext)) return 'archive'
  if (CODE_EXTS.includes(ext)) return 'code'
  if (mimeType.includes('audio/')) return 'audio'
  if (mimeType.includes('video/')) return 'video'
  if (mimeType.includes('text/')) return 'text'
  if (mimeType.includes('image/')) return 'image'
  return 'binary'
}

export const EMOJI_ICONS: Record<string, string> = {
  folder: '📁', image: '🖼️', document: '📄', archive: '🗜️',
  code: '💻', audio: '🎵', video: '🎬', text: '📝', binary: '⚙️',
}
```

- [ ] **Step 3: Write utils tests**

```typescript
// electron-app/src/main/__tests__/utils.test.ts
import { describe, it, expect } from 'vitest'
import { sanitizePathSegment, sanitizeFilename, isUrlInScope, safeJoin, defaultDownloadFolder } from '../utils'

describe('sanitizePathSegment', () => {
  it('blocks traversal patterns', () => {
    expect(sanitizePathSegment('..')).toBe('_')
    expect(sanitizePathSegment('a/b')).toBe('a_b')
    expect(sanitizePathSegment('a\\b')).toBe('a_b')
  })
  it('strips Windows-illegal chars', () => {
    expect(sanitizePathSegment('<>:"|?*')).toBe('_______')
  })
  it('returns _ for empty', () => {
    expect(sanitizePathSegment('')).toBe('_')
  })
})

describe('isUrlInScope', () => {
  it('accepts same origin and path prefix', () => {
    expect(isUrlInScope('https://example.com/a/b/', 'https://example.com/a/b/file.txt')).toBe(true)
  })
  it('rejects different host', () => {
    expect(isUrlInScope('https://example.com/a/', 'https://evil.com/a/file.txt')).toBe(false)
  })
  it('rejects different scheme', () => {
    expect(isUrlInScope('https://example.com/a/', 'http://example.com/a/file.txt')).toBe(false)
  })
})

describe('safeJoin', () => {
  it('rejects path escape', () => {
    expect(() => safeJoin('/tmp/root', ['..', 'outside.txt'])).toThrow()
  })
  it('accepts normal path', () => {
    const result = safeJoin('/tmp/root', ['sub', 'file.txt'])
    expect(result).toContain('root')
    expect(result).toContain('file.txt')
  })
})

describe('defaultDownloadFolder', () => {
  it('derives folder from hostname', () => {
    const result = defaultDownloadFolder('https://example.com/files/')
    expect(result).toContain('example.com')
  })
})
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
cd /Users/guantou/Desktop/Index-Ripper/electron-app
npx vitest run src/main/__tests__/utils.test.ts
```

Expected: FAIL — module not found

- [ ] **Step 5: Implement utils**

```typescript
// electron-app/src/main/utils.ts
import { resolve, normalize, join } from 'path'

const WINDOWS_INVALID = /[<>:"/\\|?*]/g

export function sanitizePathSegment(name: string): string {
  let value = decodeURIComponent(String(name || ''))
  value = value.replace(/[/\\]/g, '_')
  value = value.replace(WINDOWS_INVALID, '_')
  value = value.trim().replace(/[. ]+$/, '')
  if (!value || value === '.' || value === '..') return '_'
  return value
}

export function sanitizeFilename(name: string): string {
  return sanitizePathSegment(name)
}

export function isUrlInScope(baseUrl: string, candidateUrl: string): boolean {
  let base: URL, candidate: URL
  try {
    base = new URL(baseUrl)
    candidate = new URL(candidateUrl)
  } catch {
    return false
  }
  if (base.protocol !== candidate.protocol) return false
  if (base.hostname.toLowerCase() !== candidate.hostname.toLowerCase()) return false
  if (base.port !== candidate.port) return false
  const basePath = normalize(base.pathname).replace(/\/$/, '')
  const candPath = normalize(candidate.pathname)
  if (basePath === '/' || basePath === '.') return true
  return candPath === basePath || candPath.startsWith(basePath + '/')
}

export function safeJoin(root: string, parts: string[]): string {
  const rootReal = resolve(root)
  const target = resolve(join(rootReal, ...parts))
  if (!target.startsWith(rootReal)) {
    throw new Error('Path escapes root')
  }
  return target
}

export function defaultDownloadFolder(url: string): string {
  try {
    const hostname = new URL(url).hostname.replace(/:/g, '_')
    return join(require('os').homedir(), 'Downloads', hostname || 'downloads')
  } catch {
    return join(require('os').homedir(), 'Downloads', 'downloads')
  }
}

export function normalizeExtension(fileName: string): string {
  const dot = fileName.lastIndexOf('.')
  if (dot < 0) return '.(No Extension)'
  return fileName.slice(dot).toLowerCase()
}
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd /Users/guantou/Desktop/Index-Ripper/electron-app
npx vitest run src/main/__tests__/utils.test.ts
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
cd /Users/guantou/Desktop/Index-Ripper
git add electron-app/src/shared/ electron-app/src/main/utils.ts electron-app/src/main/__tests__/
git commit -m "feat(electron): add shared types, icons, and utility functions with tests"
```

---

## Task 3: Scanner Service

**Files:**
- Create: `electron-app/src/main/scanner.ts`
- Test: `electron-app/src/main/__tests__/scanner.test.ts`

- [ ] **Step 1: Write scanner tests**

```typescript
// electron-app/src/main/__tests__/scanner.test.ts
import { describe, it, expect, vi } from 'vitest'
import { parseDirectoryListing, isDirectoryHref } from '../scanner'

describe('parseDirectoryListing', () => {
  it('extracts links from Index of page', () => {
    const html = `
      <html><body>
        <a href="sub/">sub/</a>
        <a href="file.txt">file.txt</a>
        <a href="../">Parent Directory</a>
        <a href="?C=N;O=D">Name</a>
      </body></html>
    `
    const links = parseDirectoryListing(html, 'https://example.com/files/')
    expect(links).toContainEqual({ url: 'https://example.com/files/sub/', isDirectory: true })
    expect(links).toContainEqual({ url: 'https://example.com/files/file.txt', isDirectory: false })
    expect(links.find(l => l.url.includes('..'))).toBeUndefined()
    expect(links.find(l => l.url.includes('?'))).toBeUndefined()
  })

  it('ignores out-of-scope links', () => {
    const html = '<html><body><a href="https://evil.com/hack">hack</a></body></html>'
    const links = parseDirectoryListing(html, 'https://example.com/')
    expect(links).toHaveLength(0)
  })
})

describe('isDirectoryHref', () => {
  it('returns true for trailing slash', () => {
    expect(isDirectoryHref('sub/')).toBe(true)
  })
  it('returns false for files', () => {
    expect(isDirectoryHref('file.txt')).toBe(false)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/guantou/Desktop/Index-Ripper/electron-app
npx vitest run src/main/__tests__/scanner.test.ts
```

Expected: FAIL

- [ ] **Step 3: Implement scanner**

```typescript
// electron-app/src/main/scanner.ts
import * as cheerio from 'cheerio'
import { net } from 'electron'
import { basename, dirname } from 'path'
import { EventEmitter } from 'events'
import type { TreeNode } from '../shared/types'
import { isUrlInScope } from './utils'
import { getIconGroup } from '../shared/icons'

export interface ParsedLink {
  url: string
  isDirectory: boolean
}

export function isDirectoryHref(href: string): boolean {
  return href.endsWith('/')
}

export function parseDirectoryListing(html: string, pageUrl: string): ParsedLink[] {
  const $ = cheerio.load(html)
  const links: ParsedLink[] = []
  const seen = new Set<string>()

  $('a').each((_, el) => {
    const href = $(el).attr('href')
    if (!href || href === '.' || href === '..' || href === '/' || href.startsWith('?')) return
    if (href.includes('..')) return

    let fullUrl: string
    try {
      fullUrl = new URL(href, pageUrl).href
    } catch {
      return
    }

    // Strip query/fragment
    const parsed = new URL(fullUrl)
    fullUrl = `${parsed.protocol}//${parsed.host}${parsed.pathname}`

    if (!isUrlInScope(pageUrl, fullUrl)) return
    if (seen.has(fullUrl)) return
    seen.add(fullUrl)

    links.push({ url: fullUrl, isDirectory: isDirectoryHref(href) })
  })

  return links
}

export interface ScanCallbacks {
  onItem: (node: Partial<TreeNode> & { isDirectory: boolean }) => void
  onProgress: (scanned: number, total: number) => void
  onError: (message: string) => void
  onFinished: (stopped: boolean) => void
}

export class Scanner extends EventEmitter {
  private aborted = false
  private paused = false
  private pausePromise: Promise<void> | null = null
  private pauseResolve: (() => void) | null = null

  abort(): void { this.aborted = true }

  pause(): void {
    if (this.paused) return
    this.paused = true
    this.pausePromise = new Promise(r => { this.pauseResolve = r })
  }

  resume(): void {
    this.paused = false
    this.pauseResolve?.()
    this.pausePromise = null
  }

  private async waitIfPaused(): Promise<void> {
    if (this.pausePromise) await this.pausePromise
  }

  async scan(url: string, callbacks: ScanCallbacks): Promise<void> {
    try {
      // Phase 1: Discover all URLs recursively
      const allUrls = await this.discoverUrls(url, callbacks)
      if (this.aborted) { callbacks.onFinished(true); return }

      // Phase 2: Process each URL (HEAD requests for files)
      let scanned = 0
      const total = allUrls.length
      callbacks.onProgress(0, total)

      for (const item of allUrls) {
        if (this.aborted) break
        await this.waitIfPaused()

        if (item.isDirectory) {
          const dirPath = new URL(item.url).pathname.replace(/\/$/, '')
          callbacks.onItem({ isDirectory: true, fullPath: dirPath, name: basename(dirPath) || '/', kind: 'folder' })
        } else {
          await this.processFile(item.url, callbacks)
        }
        scanned++
        callbacks.onProgress(scanned, total)
      }

      callbacks.onFinished(this.aborted)
    } catch (err) {
      callbacks.onError(String(err))
      callbacks.onFinished(false)
    }
  }

  private async discoverUrls(
    url: string,
    callbacks: ScanCallbacks,
    visited = new Set<string>()
  ): Promise<ParsedLink[]> {
    const normalized = url.endsWith('/') ? url : url + '/'
    if (visited.has(normalized) || this.aborted) return []
    visited.add(normalized)

    const html = await this.fetchHtml(url)
    if (!html) return []

    const links = parseDirectoryListing(html, url)
    const result: ParsedLink[] = [...links]

    for (const link of links) {
      if (this.aborted) break
      if (link.isDirectory) {
        const subLinks = await this.discoverUrls(link.url, callbacks, visited)
        result.push(...subLinks)
      }
    }

    return result
  }

  private async fetchHtml(url: string): Promise<string | null> {
    return new Promise((resolve) => {
      const request = net.request(url)
      let data = ''
      request.on('response', (response) => {
        response.on('data', (chunk) => { data += chunk.toString() })
        response.on('end', () => resolve(data))
        response.on('error', () => resolve(null))
      })
      request.on('error', () => resolve(null))
      request.end()
    })
  }

  private async processFile(url: string, callbacks: ScanCallbacks): Promise<void> {
    const parsed = new URL(url)
    const fileName = decodeURIComponent(basename(parsed.pathname))
    const dirPath = decodeURIComponent(dirname(parsed.pathname))
    if (!fileName) return

    const fullPath = (dirPath + '/' + fileName).replace(/^\//, '')

    try {
      const head = await this.headRequest(url)
      const size = head.contentLength
        ? `${(head.contentLength / 1024).toFixed(2)} KB`
        : 'Unknown'
      const fileType = head.contentType || 'Unknown'
      const iconGroup = getIconGroup(fileName, fileType)

      callbacks.onItem({
        isDirectory: false,
        name: fileName,
        kind: 'file',
        url,
        fullPath,
        size,
        fileType,
        iconGroup,
      })
    } catch {
      callbacks.onError(`Could not process file ${url}`)
    }
  }

  private headRequest(url: string): Promise<{ contentLength: number | null; contentType: string }> {
    return new Promise((resolve, reject) => {
      const request = net.request({ url, method: 'HEAD' })
      request.on('response', (response) => {
        resolve({
          contentLength: response.headers['content-length']
            ? parseInt(String(response.headers['content-length']), 10)
            : null,
          contentType: String(response.headers['content-type'] || ''),
        })
        response.on('data', () => {}) // drain
        response.on('end', () => {})
      })
      request.on('error', reject)
      request.end()
    })
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/guantou/Desktop/Index-Ripper/electron-app
npx vitest run src/main/__tests__/scanner.test.ts
```

Expected: PASS (pure parsing tests; Scanner class needs Electron runtime for full test)

- [ ] **Step 5: Commit**

```bash
cd /Users/guantou/Desktop/Index-Ripper
git add electron-app/src/main/scanner.ts electron-app/src/main/__tests__/scanner.test.ts
git commit -m "feat(electron): implement scanner service with directory listing parser"
```

---

## Task 4: Download Manager

**Files:**
- Create: `electron-app/src/main/downloader.ts`

- [ ] **Step 1: Implement downloader**

```typescript
// electron-app/src/main/downloader.ts
import { net } from 'electron'
import { createWriteStream, mkdirSync, unlinkSync, existsSync } from 'fs'
import { dirname } from 'path'
import PQueue from 'p-queue'
import { EventEmitter } from 'events'
import type { DownloadItem } from '../shared/types'

export interface DownloadCallbacks {
  onProgress: (fileId: string, progress: number, speed: number) => void
  onStatus: (fileId: string, status: DownloadItem['status']) => void
  onFinished: (completed: number, total: number) => void
  onLog: (message: string) => void
}

export class Downloader extends EventEmitter {
  private queue: PQueue
  private aborted = false
  private paused = false
  private pausePromise: Promise<void> | null = null
  private pauseResolve: (() => void) | null = null
  private cancelledFiles = new Set<string>()

  constructor(concurrency = 5) {
    super()
    this.queue = new PQueue({ concurrency })
  }

  setConcurrency(n: number): void {
    this.queue.concurrency = Math.max(1, Math.min(10, n))
  }

  pause(): void {
    if (this.paused) return
    this.paused = true
    this.queue.pause()
    this.pausePromise = new Promise(r => { this.pauseResolve = r })
  }

  resume(): void {
    this.paused = false
    this.queue.start()
    this.pauseResolve?.()
    this.pausePromise = null
  }

  cancelFile(fileId: string): void {
    this.cancelledFiles.add(fileId)
  }

  cancelAll(): void {
    this.aborted = true
    this.queue.clear()
  }

  async downloadFiles(
    files: Array<{ id: string; url: string; destPath: string; fileName: string }>,
    callbacks: DownloadCallbacks
  ): Promise<void> {
    this.aborted = false
    this.cancelledFiles.clear()
    let completed = 0
    const total = files.length

    const tasks = files.map(file =>
      this.queue.add(async () => {
        if (this.aborted || this.cancelledFiles.has(file.id)) {
          callbacks.onStatus(file.id, 'cancelled')
          return
        }
        const success = await this.downloadOne(file, callbacks)
        if (success) completed++
      })
    )

    await Promise.allSettled(tasks)
    callbacks.onFinished(completed, total)
  }

  private async downloadOne(
    file: { id: string; url: string; destPath: string; fileName: string },
    callbacks: DownloadCallbacks,
    attempt = 1
  ): Promise<boolean> {
    callbacks.onStatus(file.id, 'downloading')

    return new Promise<boolean>((resolve) => {
      mkdirSync(dirname(file.destPath), { recursive: true })

      const request = net.request(file.url)
      request.on('response', (response) => {
        if (response.statusCode && response.statusCode >= 500 && attempt <= 3) {
          const delay = Math.pow(2, attempt) * 100
          setTimeout(() => {
            this.downloadOne(file, callbacks, attempt + 1).then(resolve)
          }, delay)
          return
        }

        const totalSize = response.headers['content-length']
          ? parseInt(String(response.headers['content-length']), 10)
          : 0
        let downloaded = 0
        let lastTime = Date.now()
        let lastBytes = 0

        const stream = createWriteStream(file.destPath)

        response.on('data', (chunk) => {
          if (this.aborted || this.cancelledFiles.has(file.id)) {
            request.abort()
            stream.close()
            this.cleanupFile(file.destPath)
            callbacks.onStatus(file.id, 'cancelled')
            callbacks.onLog(`[Download] Cancelled: ${file.fileName}`)
            resolve(false)
            return
          }

          stream.write(chunk)
          downloaded += chunk.length

          const now = Date.now()
          const elapsed = (now - lastTime) / 1000
          if (elapsed >= 0.5) {
            const speed = (downloaded - lastBytes) / elapsed
            lastTime = now
            lastBytes = downloaded
            const progress = totalSize > 0 ? (downloaded / totalSize) * 100 : 0
            callbacks.onProgress(file.id, progress, speed)
          }
        })

        response.on('end', () => {
          stream.close()
          callbacks.onProgress(file.id, 100, 0)
          callbacks.onStatus(file.id, 'completed')
          callbacks.onLog(`[Download] Completed: ${file.fileName}`)
          resolve(true)
        })

        response.on('error', (err) => {
          stream.close()
          this.cleanupFile(file.destPath)
          callbacks.onStatus(file.id, 'failed')
          callbacks.onLog(`[Download] Failed: ${file.fileName} — ${err}`)
          resolve(false)
        })
      })

      request.on('error', (err) => {
        this.cleanupFile(file.destPath)
        callbacks.onStatus(file.id, 'failed')
        callbacks.onLog(`[Download] Error: ${file.fileName} — ${err}`)
        resolve(false)
      })

      request.end()
    })
  }

  private cleanupFile(path: string): void {
    try {
      if (existsSync(path)) unlinkSync(path)
    } catch { /* ignore */ }
  }
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/guantou/Desktop/Index-Ripper
git add electron-app/src/main/downloader.ts
git commit -m "feat(electron): implement download manager with retry, cancel, pause/resume"
```

---

## Task 5: Task Queue & IPC Bridge

**Files:**
- Create: `electron-app/src/main/task-queue.ts`
- Create: `electron-app/src/main/ipc.ts`
- Modify: `electron-app/src/main/index.ts`
- Modify: `electron-app/src/preload/index.ts`

- [ ] **Step 1: Implement task queue**

```typescript
// electron-app/src/main/task-queue.ts
import { randomUUID } from 'crypto'
import type { Task } from '../shared/types'
import { Scanner } from './scanner'
import { Downloader } from './downloader'
import { defaultDownloadFolder } from './utils'

export class TaskQueue {
  tasks = new Map<string, { task: Task; scanner: Scanner; downloader: Downloader }>()

  createTask(url: string): Task {
    const id = randomUUID()
    const task: Task = {
      id,
      url,
      status: 'idle',
      nodes: {},
      roots: [],
      checkedFiles: [],
      downloads: {},
      scanProgress: { scanned: 0, total: 0 },
      downloadPath: defaultDownloadFolder(url),
    }
    this.tasks.set(id, { task, scanner: new Scanner(), downloader: new Downloader() })
    return task
  }

  getTask(taskId: string) { return this.tasks.get(taskId) }
  removeTask(taskId: string) {
    const entry = this.tasks.get(taskId)
    if (entry) {
      entry.scanner.abort()
      entry.downloader.cancelAll()
      this.tasks.delete(taskId)
    }
  }
  allTasks(): Task[] { return [...this.tasks.values()].map(e => e.task) }
}
```

- [ ] **Step 2: Implement IPC handler registration**

Create `electron-app/src/main/ipc.ts` that registers all IPC handlers listed in the spec. Each handler delegates to TaskQueue, Scanner, or Downloader. Main-to-renderer events use `webContents.send()`.

Key handlers:
- `scan:start` → creates Scanner, calls `scanner.scan()`, pipes callbacks to renderer via IPC events
- `download:start` → prepares file list, calls `downloader.downloadFiles()`
- `task:create` → creates new task, returns task data
- `dialog:selectFolder` → uses `dialog.showOpenDialog()`
- `download:setWorkers` → calls `downloader.setConcurrency()`

- [ ] **Step 3: Update preload to expose typed API**

```typescript
// electron-app/src/preload/index.ts
import { contextBridge, ipcRenderer } from 'electron'

const api = {
  // Renderer → Main
  scan: {
    start: (taskId: string, url: string) => ipcRenderer.invoke('scan:start', taskId, url),
    stop: (taskId: string) => ipcRenderer.invoke('scan:stop', taskId),
    pause: (taskId: string) => ipcRenderer.invoke('scan:pause', taskId),
    resume: (taskId: string) => ipcRenderer.invoke('scan:resume', taskId),
  },
  download: {
    start: (taskId: string, files: any[], destPath: string) =>
      ipcRenderer.invoke('download:start', taskId, files, destPath),
    pause: (taskId: string) => ipcRenderer.invoke('download:pause', taskId),
    resume: (taskId: string) => ipcRenderer.invoke('download:resume', taskId),
    cancel: (taskId: string, fileId: string) => ipcRenderer.invoke('download:cancel', taskId, fileId),
    cancelAll: (taskId: string) => ipcRenderer.invoke('download:cancelAll', taskId),
    retry: (taskId: string, fileId: string) => ipcRenderer.invoke('download:retry', taskId, fileId),
    setWorkers: (count: number) => ipcRenderer.invoke('download:setWorkers', count),
  },
  task: {
    create: (url: string) => ipcRenderer.invoke('task:create', url),
    remove: (taskId: string) => ipcRenderer.invoke('task:remove', taskId),
  },
  settings: {
    get: () => ipcRenderer.invoke('settings:get'),
    set: (data: any) => ipcRenderer.invoke('settings:set', data),
  },
  dialog: {
    selectFolder: () => ipcRenderer.invoke('dialog:selectFolder'),
  },
  // Main → Renderer (event subscriptions)
  on: (channel: string, callback: (...args: any[]) => void) => {
    const listener = (_event: any, ...args: any[]) => callback(...args)
    ipcRenderer.on(channel, listener)
    return () => ipcRenderer.removeListener(channel, listener)
  },
}

contextBridge.exposeInMainWorld('api', api)
```

- [ ] **Step 4: Update main/index.ts to register IPC handlers on app ready**

Wire up `registerIpcHandlers(taskQueue)` call in the `app.whenReady()` block.

- [ ] **Step 5: Verify app still launches**

```bash
cd /Users/guantou/Desktop/Index-Ripper/electron-app
npm run dev
```

Expected: Electron window opens without errors

- [ ] **Step 6: Commit**

```bash
cd /Users/guantou/Desktop/Index-Ripper
git add electron-app/src/main/ electron-app/src/preload/
git commit -m "feat(electron): implement task queue, IPC bridge, and preload API"
```

---

## Task 6: Zustand Stores

**Files:**
- Create: `electron-app/src/renderer/stores/task-store.ts`
- Create: `electron-app/src/renderer/stores/tree-store.ts`
- Create: `electron-app/src/renderer/stores/download-store.ts`
- Create: `electron-app/src/renderer/hooks/useIpc.ts`

- [ ] **Step 1: Create IPC subscription hook**

```typescript
// electron-app/src/renderer/hooks/useIpc.ts
import { useEffect } from 'react'

declare global {
  interface Window { api: any }
}

export function useIpcEvent(channel: string, callback: (...args: any[]) => void): void {
  useEffect(() => {
    const unsubscribe = window.api.on(channel, callback)
    return unsubscribe
  }, [channel, callback])
}
```

- [ ] **Step 2: Create task store**

```typescript
// electron-app/src/renderer/stores/task-store.ts
import { create } from 'zustand'
import type { Task } from '../../shared/types'

interface TaskStore {
  tasks: Record<string, Task>
  activeTaskId: string | null
  createTask: (task: Task) => void
  removeTask: (taskId: string) => void
  setActiveTask: (taskId: string) => void
  updateTask: (taskId: string, partial: Partial<Task>) => void
}

export const useTaskStore = create<TaskStore>((set) => ({
  tasks: {},
  activeTaskId: null,
  createTask: (task) => set((state) => ({
    tasks: { ...state.tasks, [task.id]: task },
    activeTaskId: state.activeTaskId ?? task.id,
  })),
  removeTask: (taskId) => set((state) => {
    const { [taskId]: _, ...rest } = state.tasks
    const ids = Object.keys(rest)
    return {
      tasks: rest,
      activeTaskId: state.activeTaskId === taskId ? (ids[0] ?? null) : state.activeTaskId,
    }
  }),
  setActiveTask: (taskId) => set({ activeTaskId: taskId }),
  updateTask: (taskId, partial) => set((state) => ({
    tasks: {
      ...state.tasks,
      [taskId]: { ...state.tasks[taskId], ...partial },
    },
  })),
}))
```

- [ ] **Step 3: Create tree and download stores**

Similar pattern — `useTreeStore` manages nodes/roots/checked per task, `useDownloadStore` manages download items per task. Both update from IPC events.

- [ ] **Step 4: Commit**

```bash
cd /Users/guantou/Desktop/Index-Ripper
git add electron-app/src/renderer/stores/ electron-app/src/renderer/hooks/
git commit -m "feat(electron): add Zustand stores for tasks, tree, and downloads"
```

---

## Task 7: UI Shell — TaskTabs + Toolbar + SplitPanel

**Files:**
- Create: `electron-app/src/renderer/components/TaskTabs.tsx`
- Create: `electron-app/src/renderer/components/Toolbar.tsx`
- Create: `electron-app/src/renderer/components/SplitPanel.tsx`
- Modify: `electron-app/src/renderer/App.tsx`

- [ ] **Step 1: Build TaskTabs component**

Tab bar showing all tasks. Each tab displays shortened hostname. `+` button to create new task. Active tab highlighted.

- [ ] **Step 2: Build Toolbar component**

URL input, Scan/Stop button, Download button, thread count dropdown, status indicator (dot + text).

- [ ] **Step 3: Build SplitPanel component**

Resizable left/right panels using CSS `resize` or a drag handle. Left panel takes ~40% default width.

- [ ] **Step 4: Assemble in App.tsx**

```tsx
export default function App() {
  return (
    <div className="h-screen bg-slate-950 text-slate-100 flex flex-col">
      <TaskTabs />
      <Toolbar />
      <SplitPanel
        left={<div>File Tree (coming next)</div>}
        right={<div>Downloads/Logs (coming next)</div>}
      />
    </div>
  )
}
```

- [ ] **Step 5: Verify layout renders correctly**

```bash
cd /Users/guantou/Desktop/Index-Ripper/electron-app && npm run dev
```

Expected: Window shows task tabs, toolbar with URL input, and split panel layout.

- [ ] **Step 6: Commit**

```bash
cd /Users/guantou/Desktop/Index-Ripper
git add electron-app/src/renderer/
git commit -m "feat(electron): build UI shell with TaskTabs, Toolbar, SplitPanel"
```

---

## Task 8: FileTree Component

**Files:**
- Create: `electron-app/src/renderer/components/FileTree.tsx`
- Create: `electron-app/src/renderer/components/FileTreeRow.tsx`
- Create: `electron-app/src/renderer/hooks/useFileTree.ts`
- Create: `electron-app/src/renderer/components/SearchBar.tsx`
- Create: `electron-app/src/renderer/components/TypeFilters.tsx`
- Create: `electron-app/src/renderer/components/StatusBar.tsx`

- [ ] **Step 1: Create useFileTree hook**

Logic for: flatten tree to visible list (respecting expanded/hidden), toggle check (with folder cascade), expand/collapse, search filter, type filter.

- [ ] **Step 2: Create FileTreeRow component**

Single row: 3px accent bar + indent spacer + emoji icon + name + size (files) or chevron (folders). Hover effect, click to toggle check.

- [ ] **Step 3: Create FileTree component**

Uses `@tanstack/react-virtual` to virtualize the flattened visible node list. Right-click context menu using shadcn ContextMenu.

- [ ] **Step 4: Create SearchBar, TypeFilters, StatusBar**

- SearchBar: input field, Ctrl+F focuses it, Escape clears
- TypeFilters: horizontal scrollable row of checkbox chips with counts
- StatusBar: "20 files, 3 folders | 2 selected"

- [ ] **Step 5: Wire into SplitPanel left side**

- [ ] **Step 6: Verify with mock data**

Manually add some TreeNode data to the store and verify the tree renders, expands, collapses, and checkboxes work.

- [ ] **Step 7: Commit**

```bash
cd /Users/guantou/Desktop/Index-Ripper
git add electron-app/src/renderer/
git commit -m "feat(electron): implement FileTree with virtual scrolling, search, type filters"
```

---

## Task 9: Downloads Panel + Logs Panel

**Files:**
- Create: `electron-app/src/renderer/components/DownloadsList.tsx`
- Create: `electron-app/src/renderer/components/DownloadCard.tsx`
- Create: `electron-app/src/renderer/components/LogsPanel.tsx`

- [ ] **Step 1: Build DownloadCard**

Card showing: file name, progress bar (shadcn Progress), status text (color-coded), speed display, cancel/retry button.

- [ ] **Step 2: Build DownloadsList**

Scrollable list of DownloadCards. Overall progress bar + ETA at bottom.

- [ ] **Step 3: Build LogsPanel**

Scrollable monospace text area, auto-scrolls to bottom. Receives `log:message` IPC events.

- [ ] **Step 4: Wire into SplitPanel right side with tab switching**

Use shadcn Tabs to switch between Downloads and Logs.

- [ ] **Step 5: Commit**

```bash
cd /Users/guantou/Desktop/Index-Ripper
git add electron-app/src/renderer/
git commit -m "feat(electron): implement DownloadsList, DownloadCard, LogsPanel"
```

---

## Task 10: IPC Integration — Connect UI to Backend

**Files:**
- Modify: `electron-app/src/renderer/components/Toolbar.tsx`
- Modify: `electron-app/src/renderer/components/TaskTabs.tsx`
- Modify: `electron-app/src/renderer/App.tsx`
- Modify: `electron-app/src/renderer/stores/*.ts`

- [ ] **Step 1: Wire scan flow**

Toolbar "Scan" button → `window.api.scan.start(taskId, url)`. Subscribe to `scan:item`, `scan:progress`, `scan:finished`, `scan:error` events → update tree store and task store.

- [ ] **Step 2: Wire download flow**

Toolbar "Download" button → collect checked files → `window.api.download.start(taskId, files, destPath)`. Subscribe to `download:progress`, `download:status`, `download:finished` → update download store.

- [ ] **Step 3: Wire task management**

TaskTabs `+` button → `window.api.task.create(url)`. Tab close → `window.api.task.remove(taskId)`. Tab click → switch active task in store.

- [ ] **Step 4: Wire settings persistence**

On window close → save panel sizes, thread count, last download path via `window.api.settings.set()`. On app start → restore via `window.api.settings.get()`.

- [ ] **Step 5: Add toast notifications**

Use shadcn Sonner for: scan complete, download complete, errors.

- [ ] **Step 6: Full integration test**

Launch app, enter a real "Index of" URL, scan, select files, download. Verify complete flow.

- [ ] **Step 7: Commit**

```bash
cd /Users/guantou/Desktop/Index-Ripper
git add electron-app/
git commit -m "feat(electron): integrate IPC between UI and backend, full scan/download flow"
```

---

## Task 11: Packaging & Build Configuration

**Files:**
- Modify: `electron-app/electron-builder.yml`
- Modify: `electron-app/package.json`

- [ ] **Step 1: Configure electron-builder.yml**

```yaml
appId: com.indexripper.app
productName: Index Ripper
directories:
  buildResources: resources
  output: dist
files:
  - '!**/.vscode/*'
  - '!src/*'
  - '!electron.vite.config.*'
  - '!{.eslintignore,.eslintrc.cjs,.prettierignore,.prettierrc.yaml,dev-app-update.yml,CHANGELOG.md,README.md}'
win:
  target: nsis
  icon: resources/icon.ico
mac:
  target: dmg
  icon: resources/icon.png
  category: public.app-category.utilities
linux:
  target: AppImage
  icon: resources/icon.png
  category: Utility
```

- [ ] **Step 2: Add build scripts to package.json**

```json
{
  "scripts": {
    "build": "electron-vite build",
    "build:win": "npm run build && electron-builder --win",
    "build:mac": "npm run build && electron-builder --mac",
    "build:linux": "npm run build && electron-builder --linux"
  }
}
```

- [ ] **Step 3: Test build**

```bash
cd /Users/guantou/Desktop/Index-Ripper/electron-app
npm run build
```

Expected: Build succeeds, output in `dist/`

- [ ] **Step 4: Commit**

```bash
cd /Users/guantou/Desktop/Index-Ripper
git add electron-app/
git commit -m "build(electron): configure electron-builder for cross-platform packaging"
```

---

## Task 12: Final Verification & Cleanup

- [ ] **Step 1: Run all tests**

```bash
cd /Users/guantou/Desktop/Index-Ripper/electron-app
npx vitest run
```

- [ ] **Step 2: Verify complete flow**

1. `npm run dev` → app launches
2. Enter URL → Scan → file tree populates
3. Check files → Download → progress shows
4. Pause/resume scan and download
5. Add second task tab → switch between tasks
6. Cancel individual download
7. Change thread count

- [ ] **Step 3: Update .gitignore**

Add `electron-app/node_modules/`, `electron-app/dist/`, `electron-app/out/` to root `.gitignore`.

- [ ] **Step 4: Final commit**

```bash
cd /Users/guantou/Desktop/Index-Ripper
git add -A
git commit -m "feat(electron): complete Electron rewrite with full feature parity"
```
