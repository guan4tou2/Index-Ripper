import * as cheerio from 'cheerio'
import { isUrlInScope } from './utils'
import { getIconGroup } from '../shared/icons'
import type { TreeNode } from '../shared/types'

// ---------------------------------------------------------------------------
// Pure helpers (testable without Electron)
// ---------------------------------------------------------------------------

export interface ParsedLink {
  url: string
  isDirectory: boolean
}

/**
 * Returns true if the href likely represents a directory.
 * Heuristic: ends with '/' OR has no file extension (no '.' in the last segment).
 */
export function isDirectoryHref(href: string): boolean {
  if (!href) return false
  if (href.endsWith('/')) return true
  // No extension = likely a directory (e.g., "/docs", "/electron-app")
  const lastSegment = href.split('/').filter(Boolean).pop() ?? ''
  if (!lastSegment) return false
  return !lastSegment.includes('.')
}

/**
 * Parse an "Index of" HTML page and return links that are in scope.
 *
 * Filters out:
 *  - `.`  (current directory)
 *  - `..` and links starting with `..`
 *  - `/`  (root)
 *  - Links beginning with `?` (sort query params)
 *  - Links that are out of scope relative to pageUrl
 */
export function parseDirectoryListing(html: string, pageUrl: string): ParsedLink[] {
  const $ = cheerio.load(html)
  const results: ParsedLink[] = []
  const seen = new Set<string>()

  $('a[href]').each((_i, el) => {
    const href = $(el).attr('href') ?? ''

    // Skip navigation / query links
    if (href === '.' || href === './' || href === '..' || href === '../') return
    if (href.startsWith('..')) return
    if (href === '/') return
    if (href.startsWith('?')) return
    if (href === '') return

    // Resolve to absolute URL
    let absoluteUrl: string
    try {
      const parsed = new URL(href, pageUrl)
      // Skip links with query strings (e.g., "?view", "?C=N;O=D")
      if (parsed.search) return
      absoluteUrl = `${parsed.protocol}//${parsed.host}${parsed.pathname}`
    } catch {
      return
    }

    // Scope check
    if (!isUrlInScope(pageUrl, absoluteUrl)) return

    // Deduplicate
    if (seen.has(absoluteUrl)) return
    seen.add(absoluteUrl)

    results.push({ url: absoluteUrl, isDirectory: isDirectoryHref(href) })
  })

  return results
}

// ---------------------------------------------------------------------------
// Scanner callbacks interface
// ---------------------------------------------------------------------------

export interface ScanCallbacks {
  onItem: (node: TreeNode, parentId: string) => void
  onProgress: (scanned: number, total: number) => void
  onError: (url: string, err: Error) => void
  onFinished: () => void
}

// ---------------------------------------------------------------------------
// Scanner class
// ---------------------------------------------------------------------------

/**
 * A fetch function compatible with the native `fetch` API (subset).
 * Accepts a URL string and an optional init, returns a Response-like object.
 */
export type FetchFn = (
  url: string,
  init?: { method?: string; signal?: AbortSignal }
) => Promise<{
  ok: boolean
  status: number
  text(): Promise<string>
  headers: { get(name: string): string | null }
}>

/** Generate a simple deterministic node ID from a URL. */
function urlToId(url: string): string {
  // Use a simple hash-like approach; collision risk is negligible for a scan session
  return url.replace(/[^a-zA-Z0-9]/g, '_')
}

/** Format a byte count as a human-readable string. */
function formatSize(bytes: number | null): string {
  if (bytes === null || bytes < 0) return 'Unknown'
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  const val = bytes / Math.pow(1024, i)
  return `${val.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

/** Extract filename from a URL path. */
function fileNameFromUrl(url: string): string {
  try {
    const pathname = new URL(url).pathname
    const parts = pathname.replace(/\/$/, '').split('/')
    return decodeURIComponent(parts[parts.length - 1] || '')
  } catch {
    return url
  }
}

/** Derive the relative path of a URL under a base URL. */
function relativePathFromBase(baseUrl: string, targetUrl: string): string {
  try {
    const base = new URL(baseUrl)
    const target = new URL(targetUrl)
    const basePath = base.pathname.endsWith('/') ? base.pathname : base.pathname + '/'
    const rel = target.pathname.slice(basePath.length)
    return rel || ''
  } catch {
    return ''
  }
}

export class Scanner {
  private aborted = false
  private paused = false
  private resumeResolve: (() => void) | null = null
  private fetchFn: FetchFn

  constructor(fetchFn?: FetchFn) {
    if (fetchFn) {
      this.fetchFn = fetchFn
    } else {
      // Use Electron net module wrapped as fetch, falling back to global fetch
      this.fetchFn = this.electronFetch.bind(this)
    }
  }

  // ---------------------------------------------------------------------------
  // Electron net-based fetch (used at runtime)
  // ---------------------------------------------------------------------------

  private async electronFetch(
    url: string,
    init?: { method?: string; signal?: AbortSignal }
  ): Promise<{
    ok: boolean
    status: number
    text(): Promise<string>
    headers: { get(name: string): string | null }
  }> {
    // Use Node.js built-in fetch (available in Node 18+).
    // Electron's net.fetch can force HTTPS upgrades on HTTP URLs, causing
    // TLS handshake errors against plain HTTP servers.
    const fetchImpl = globalThis.fetch as unknown as FetchFn
    return fetchImpl(url, init)
  }

  // ---------------------------------------------------------------------------
  // Pause / resume support
  // ---------------------------------------------------------------------------

  pause(): void {
    this.paused = true
  }

  resume(): void {
    if (!this.paused) return
    this.paused = false
    if (this.resumeResolve) {
      this.resumeResolve()
      this.resumeResolve = null
    }
  }

  private waitIfPaused(): Promise<void> {
    if (!this.paused) return Promise.resolve()
    return new Promise<void>((resolve) => {
      this.resumeResolve = resolve
    })
  }

  // ---------------------------------------------------------------------------
  // Abort
  // ---------------------------------------------------------------------------

  abort(): void {
    this.aborted = true
    // Unblock any waiting pause
    if (this.resumeResolve) {
      this.resumeResolve()
      this.resumeResolve = null
    }
  }

  // ---------------------------------------------------------------------------
  // Fetch helpers
  // ---------------------------------------------------------------------------

  /** Fetch HTML from a directory URL. */
  protected async fetchHtml(url: string): Promise<string> {
    const response = await this.fetchFn(url)
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} fetching ${url}`)
    }
    return response.text()
  }

  /** Issue a HEAD request and return { size, mimeType }. */
  private async headRequest(url: string): Promise<{ size: number | null; mimeType: string }> {
    try {
      const response = await this.fetchFn(url, { method: 'HEAD' })
      const lengthHeader = response.headers.get('content-length')
      const size = lengthHeader !== null ? parseInt(lengthHeader, 10) : null
      const mimeType = response.headers.get('content-type') ?? ''
      return { size, mimeType: mimeType.split(';')[0].trim() }
    } catch {
      return { size: null, mimeType: '' }
    }
  }

  // ---------------------------------------------------------------------------
  // Main scan
  // ---------------------------------------------------------------------------

  private maxDepth = 20

  async scan(rootUrl: string, callbacks: ScanCallbacks): Promise<void> {
    this.aborted = false
    this.paused = false

    // ------------------------------------------------------------------
    // Phase 1: Discovery — recursively collect all URLs
    // ------------------------------------------------------------------
    interface DiscoveredEntry {
      url: string
      isDirectory: boolean
      parentId: string
      depth: number
    }

    const discovered: DiscoveredEntry[] = []
    const visitedDirs = new Set<string>()

    // Iterative BFS discovery
    const queue: Array<{ url: string; parentId: string; depth: number }> = [
      { url: rootUrl, parentId: '', depth: 0 },
    ]

    while (queue.length > 0 && !this.aborted) {
      await this.waitIfPaused()
      if (this.aborted) break

      const { url, parentId, depth } = queue.shift()!

      if (visitedDirs.has(url)) continue
      visitedDirs.add(url)

      let html: string
      try {
        html = await this.fetchHtml(url)
      } catch (err) {
        callbacks.onError(url, err instanceof Error ? err : new Error(String(err)))
        continue
      }

      const links = parseDirectoryListing(html, url)
      for (const link of links) {
        discovered.push({ url: link.url, isDirectory: link.isDirectory, parentId, depth })
        if (link.isDirectory && !visitedDirs.has(link.url) && depth < this.maxDepth) {
          queue.push({ url: link.url, parentId: urlToId(link.url), depth: depth + 1 })
        }
      }
    }

    if (this.aborted) {
      callbacks.onFinished()
      return
    }

    // ------------------------------------------------------------------
    // Phase 2: Process each discovered entry
    // ------------------------------------------------------------------
    const total = discovered.length
    let scanned = 0
    callbacks.onProgress(scanned, total)

    for (const entry of discovered) {
      await this.waitIfPaused()
      if (this.aborted) break

      const name = fileNameFromUrl(entry.url)
      const nodeId = urlToId(entry.url)
      const fullPath = relativePathFromBase(rootUrl, entry.url)

      if (entry.isDirectory) {
        const node: TreeNode = {
          id: nodeId,
          parentId: entry.parentId,
          name,
          kind: 'folder',
          url: '',
          fullPath,
          size: 'Unknown',
          fileType: '',
          iconGroup: 'folder',
          checked: false,
          expanded: false,
          hidden: false,
          children: [],
        }
        callbacks.onItem(node, entry.parentId)
      } else {
        // HEAD request for file metadata
        const { size, mimeType } = await this.headRequest(entry.url)

        // Heuristic: if HEAD returns text/html and name has no extension, treat as directory
        const isHtmlDir = mimeType.includes('text/html') && !name.includes('.')
        if (isHtmlDir) {
          const node: TreeNode = {
            id: nodeId,
            parentId: entry.parentId,
            name,
            kind: 'folder',
            url: '',
            fullPath,
            size: '',
            fileType: '',
            iconGroup: 'folder',
            checked: false,
            expanded: false,
            hidden: false,
            children: [],
          }
          callbacks.onItem(node, entry.parentId)
        } else {
          const node: TreeNode = {
            id: nodeId,
            parentId: entry.parentId,
            name,
            kind: 'file',
            url: entry.url,
            fullPath,
            size: formatSize(size),
            fileType: mimeType,
            iconGroup: getIconGroup(name, mimeType),
            checked: false,
            expanded: false,
            hidden: false,
            children: [],
          }
          callbacks.onItem(node, entry.parentId)
        }
      }

      scanned++
      callbacks.onProgress(scanned, total)
    }

    callbacks.onFinished()
  }
}
