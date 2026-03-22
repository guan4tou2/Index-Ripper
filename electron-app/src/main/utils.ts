import { join, resolve, extname } from 'path'
import { homedir } from 'os'

/**
 * Strip path traversal sequences and illegal characters from a single path segment.
 * Removes: `..`, `/`, `\`, and Windows-illegal chars (`<>:"|?*` and control chars).
 */
export function sanitizePathSegment(name: string): string {
  // Remove path traversal
  let sanitized = name.replace(/\.\./g, '')
  // Remove path separators
  sanitized = sanitized.replace(/[/\\]/g, '')
  // Remove Windows-illegal characters: < > : " | ? * and control chars (0x00-0x1f)
  // eslint-disable-next-line no-control-regex
  sanitized = sanitized.replace(/[<>:"|?*\x00-\x1f]/g, '')
  return sanitized
}

/**
 * Alias for sanitizePathSegment — sanitizes a file name.
 */
export function sanitizeFilename(name: string): string {
  return sanitizePathSegment(name)
}

/**
 * Returns true if candidateUrl shares the same origin and has the same
 * path prefix as baseUrl.
 */
export function isUrlInScope(baseUrl: string, candidateUrl: string): boolean {
  try {
    const base = new URL(baseUrl)
    const candidate = new URL(candidateUrl)

    if (base.origin !== candidate.origin) {
      return false
    }

    // Normalize base path to end with '/' so prefix check works correctly
    const basePath = base.pathname.endsWith('/') ? base.pathname : base.pathname + '/'
    return candidate.pathname.startsWith(basePath)
  } catch {
    return false
  }
}

/**
 * Safely joins root with parts, throwing if the resolved path would escape root.
 */
export function safeJoin(root: string, parts: string[]): string {
  const resolvedRoot = resolve(root)
  const joined = join(resolvedRoot, ...parts)
  const resolvedJoined = resolve(joined)

  if (!resolvedJoined.startsWith(resolvedRoot + '/') && resolvedJoined !== resolvedRoot) {
    throw new Error(`Path traversal detected: "${resolvedJoined}" escapes root "${resolvedRoot}"`)
  }

  return resolvedJoined
}

/**
 * Derive a default download folder from the URL hostname, placed in ~/Downloads/.
 * E.g. https://example.com/files/ → ~/Downloads/example.com
 */
export function defaultDownloadFolder(url: string): string {
  try {
    const parsed = new URL(url)
    const hostname = parsed.hostname
    return join(homedir(), 'Downloads', hostname)
  } catch {
    return join(homedir(), 'Downloads', 'index-ripper')
  }
}

/**
 * Extract the lowercase file extension from a filename.
 * Returns "" if none.
 */
export function normalizeExtension(fileName: string): string {
  return extname(fileName).toLowerCase()
}
