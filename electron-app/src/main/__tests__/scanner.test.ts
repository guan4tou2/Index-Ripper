import { describe, it, expect } from 'vitest'
import { parseDirectoryListing, isDirectoryHref } from '../scanner'

// ---------------------------------------------------------------------------
// isDirectoryHref
// ---------------------------------------------------------------------------

describe('isDirectoryHref', () => {
  it('returns true for hrefs ending with /', () => {
    expect(isDirectoryHref('subdir/')).toBe(true)
    expect(isDirectoryHref('/')).toBe(true)
    expect(isDirectoryHref('deep/nested/')).toBe(true)
  })

  it('returns false for hrefs with file extensions', () => {
    expect(isDirectoryHref('file.txt')).toBe(false)
    expect(isDirectoryHref('archive.tar.gz')).toBe(false)
    expect(isDirectoryHref('')).toBe(false)
  })

  it('returns true for hrefs without extension (directory heuristic)', () => {
    expect(isDirectoryHref('subdir')).toBe(true)
    expect(isDirectoryHref('/docs')).toBe(true)
    expect(isDirectoryHref('/electron-app')).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// parseDirectoryListing
// ---------------------------------------------------------------------------

/** Minimal "Index of" HTML fixture */
const SAMPLE_HTML = `
<!DOCTYPE html>
<html>
<head><title>Index of /files/</title></head>
<body>
<h1>Index of /files/</h1>
<table>
  <tr><th>Name</th><th>Size</th></tr>
  <tr><td><a href="?C=N&O=D">Name</a></td></tr>
  <tr><td><a href="/files/../">Parent Directory</a></td></tr>
  <tr><td><a href="../">Parent Directory (dotdot)</a></td></tr>
  <tr><td><a href="./">Current Directory</a></td></tr>
  <tr><td><a href=".">Dot</a></td></tr>
  <tr><td><a href="/">Root</a></td></tr>
  <tr><td><a href="subdir/">subdir/</a></td></tr>
  <tr><td><a href="file.txt">file.txt</a></td></tr>
  <tr><td><a href="archive.tar.gz">archive.tar.gz</a></td></tr>
  <tr><td><a href="https://other.com/file.txt">Out of scope</a></td></tr>
  <tr><td><a href="https://example.com/files/another.mp4">another.mp4 (absolute in scope)</a></td></tr>
  <tr><td><a href="file.txt?view">file.txt view link</a></td></tr>
</table>
</body>
</html>
`

describe('parseDirectoryListing', () => {
  const pageUrl = 'https://example.com/files/'

  it('extracts in-scope file and directory links', () => {
    const results = parseDirectoryListing(SAMPLE_HTML, pageUrl)
    const urls = results.map((r) => r.url)

    expect(urls).toContain('https://example.com/files/subdir/')
    expect(urls).toContain('https://example.com/files/file.txt')
    expect(urls).toContain('https://example.com/files/archive.tar.gz')
    expect(urls).toContain('https://example.com/files/another.mp4')
  })

  it('marks directories (trailing-slash hrefs) as isDirectory = true', () => {
    const results = parseDirectoryListing(SAMPLE_HTML, pageUrl)
    const subdir = results.find((r) => r.url === 'https://example.com/files/subdir/')
    expect(subdir).toBeDefined()
    expect(subdir!.isDirectory).toBe(true)
  })

  it('marks files (no trailing slash) as isDirectory = false', () => {
    const results = parseDirectoryListing(SAMPLE_HTML, pageUrl)
    const file = results.find((r) => r.url === 'https://example.com/files/file.txt')
    expect(file).toBeDefined()
    expect(file!.isDirectory).toBe(false)
  })

  it('skips .. / dotdot links', () => {
    const results = parseDirectoryListing(SAMPLE_HTML, pageUrl)
    const urls = results.map((r) => r.url)
    // None of the parent-directory links should appear
    for (const url of urls) {
      expect(url).not.toContain('/files/../')
    }
    // Also href="../" should be skipped — it resolves to the parent, which is out of scope anyway,
    // but we want to confirm it doesn't slip through the filter
    expect(urls).not.toContain('https://example.com/')
  })

  it('skips links beginning with ? and links with query strings', () => {
    const results = parseDirectoryListing(SAMPLE_HTML, pageUrl)
    // ?C=N&O=D is a sort query parameter link common in Apache listings
    const sortLink = results.find((r) => r.url.includes('C=N'))
    expect(sortLink).toBeUndefined()
    // file.txt?view should also be filtered
    const viewLink = results.find((r) => r.url.includes('?view'))
    expect(viewLink).toBeUndefined()
  })

  it('skips the root / link', () => {
    const results = parseDirectoryListing(SAMPLE_HTML, pageUrl)
    const rootLink = results.find((r) => r.url === 'https://example.com/')
    expect(rootLink).toBeUndefined()
  })

  it('skips . and ./ current-directory links', () => {
    const results = parseDirectoryListing(SAMPLE_HTML, pageUrl)
    // "." resolves to the page URL itself; "./" also resolves to the page URL
    // The page URL is the base — it is NOT a child, so isUrlInScope should reject it
    // (or the explicit "." / "./" filter catches it first)
    const selfLink = results.find((r) => r.url === pageUrl)
    expect(selfLink).toBeUndefined()
  })

  it('skips out-of-scope links', () => {
    const results = parseDirectoryListing(SAMPLE_HTML, pageUrl)
    const outOfScope = results.find((r) => r.url.includes('other.com'))
    expect(outOfScope).toBeUndefined()
  })

  it('deduplicates identical links', () => {
    const html = `
      <a href="file.txt">link1</a>
      <a href="file.txt">link2</a>
    `
    const results = parseDirectoryListing(html, pageUrl)
    const matches = results.filter((r) => r.url === 'https://example.com/files/file.txt')
    expect(matches).toHaveLength(1)
  })

  it('returns an empty array for a page with no links', () => {
    const results = parseDirectoryListing('<html><body>No links here</body></html>', pageUrl)
    expect(results).toHaveLength(0)
  })

  it('handles absolute in-scope links correctly', () => {
    const results = parseDirectoryListing(SAMPLE_HTML, pageUrl)
    const abs = results.find((r) => r.url === 'https://example.com/files/another.mp4')
    expect(abs).toBeDefined()
    expect(abs!.isDirectory).toBe(false)
  })
})
