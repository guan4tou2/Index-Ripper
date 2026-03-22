import { describe, it, expect } from 'vitest'
import { join } from 'path'
import { homedir } from 'os'
import {
  sanitizePathSegment,
  sanitizeFilename,
  isUrlInScope,
  safeJoin,
  defaultDownloadFolder,
  normalizeExtension,
} from '../utils'

describe('sanitizePathSegment', () => {
  it('removes path traversal sequences', () => {
    expect(sanitizePathSegment('../etc/passwd')).not.toContain('..')
    expect(sanitizePathSegment('../../secret')).not.toContain('..')
  })

  it('removes forward slashes', () => {
    expect(sanitizePathSegment('foo/bar')).toBe('foobar')
  })

  it('removes backslashes', () => {
    expect(sanitizePathSegment('foo\\bar')).toBe('foobar')
  })

  it('removes Windows-illegal characters', () => {
    expect(sanitizePathSegment('file<name>.txt')).not.toMatch(/[<>:"|?*]/)
    expect(sanitizePathSegment('file:name')).not.toContain(':')
    expect(sanitizePathSegment('file|name')).not.toContain('|')
    expect(sanitizePathSegment('file?name')).not.toContain('?')
    expect(sanitizePathSegment('file*name')).not.toContain('*')
  })

  it('removes control characters', () => {
    expect(sanitizePathSegment('file\x00name')).not.toContain('\x00')
    expect(sanitizePathSegment('file\x1fname')).not.toContain('\x1f')
  })

  it('passes through normal filenames unchanged', () => {
    expect(sanitizePathSegment('hello-world_2024.tar.gz')).toBe('hello-world_2024.tar.gz')
    expect(sanitizePathSegment('normalfile.txt')).toBe('normalfile.txt')
  })
})

describe('sanitizeFilename', () => {
  it('is an alias for sanitizePathSegment', () => {
    expect(sanitizeFilename('../foo/bar')).toBe(sanitizePathSegment('../foo/bar'))
    expect(sanitizeFilename('normal.txt')).toBe('normal.txt')
  })
})

describe('isUrlInScope', () => {
  it('returns true when candidate is under base path', () => {
    expect(isUrlInScope('https://example.com/files/', 'https://example.com/files/foo.txt')).toBe(true)
    expect(isUrlInScope('https://example.com/files/', 'https://example.com/files/sub/bar.txt')).toBe(true)
  })

  it('returns true when base URL has no trailing slash', () => {
    expect(isUrlInScope('https://example.com/files', 'https://example.com/files/foo.txt')).toBe(true)
  })

  it('returns false when candidate is at a sibling path', () => {
    expect(isUrlInScope('https://example.com/files/', 'https://example.com/other/foo.txt')).toBe(false)
  })

  it('returns false when origins differ', () => {
    expect(isUrlInScope('https://example.com/files/', 'https://evil.com/files/foo.txt')).toBe(false)
  })

  it('returns false when protocol differs', () => {
    expect(isUrlInScope('https://example.com/files/', 'http://example.com/files/foo.txt')).toBe(false)
  })

  it('returns false for invalid URLs', () => {
    expect(isUrlInScope('not-a-url', 'https://example.com/files/')).toBe(false)
    expect(isUrlInScope('https://example.com/', 'not-a-url')).toBe(false)
  })

  it('returns false when candidate is a parent of base', () => {
    expect(isUrlInScope('https://example.com/files/sub/', 'https://example.com/files/')).toBe(false)
  })
})

describe('safeJoin', () => {
  it('returns the resolved path for safe inputs', () => {
    const root = '/tmp/downloads'
    expect(safeJoin(root, ['subdir', 'file.txt'])).toBe('/tmp/downloads/subdir/file.txt')
  })

  it('throws on path traversal attempt', () => {
    const root = '/tmp/downloads'
    expect(() => safeJoin(root, ['..', 'etc', 'passwd'])).toThrow()
    expect(() => safeJoin(root, ['subdir', '..', '..', 'etc'])).toThrow()
  })

  it('handles empty parts array', () => {
    const root = '/tmp/downloads'
    expect(safeJoin(root, [])).toBe('/tmp/downloads')
  })

  it('handles a single safe part', () => {
    const root = '/tmp/downloads'
    expect(safeJoin(root, ['myfile.zip'])).toBe('/tmp/downloads/myfile.zip')
  })
})

describe('defaultDownloadFolder', () => {
  it('derives folder from URL hostname', () => {
    const result = defaultDownloadFolder('https://example.com/files/')
    expect(result).toBe(join(homedir(), 'Downloads', 'example.com'))
  })

  it('handles URLs without trailing slash', () => {
    const result = defaultDownloadFolder('https://example.com')
    expect(result).toBe(join(homedir(), 'Downloads', 'example.com'))
  })

  it('uses subdomain in folder name', () => {
    const result = defaultDownloadFolder('https://files.example.com/data/')
    expect(result).toBe(join(homedir(), 'Downloads', 'files.example.com'))
  })

  it('falls back gracefully on invalid URL', () => {
    const result = defaultDownloadFolder('not-a-url')
    expect(result).toBe(join(homedir(), 'Downloads', 'index-ripper'))
  })
})

describe('normalizeExtension', () => {
  it('returns lowercase extension with dot', () => {
    expect(normalizeExtension('file.TXT')).toBe('.txt')
    expect(normalizeExtension('archive.TAR.GZ')).toBe('.gz')
    expect(normalizeExtension('image.PNG')).toBe('.png')
  })

  it('returns empty string for files with no extension', () => {
    expect(normalizeExtension('Makefile')).toBe('')
    expect(normalizeExtension('README')).toBe('')
  })

  it('returns the extension as-is when already lowercase', () => {
    expect(normalizeExtension('script.js')).toBe('.js')
    expect(normalizeExtension('data.json')).toBe('.json')
  })

  it('handles dotfiles', () => {
    // .gitignore has no extension — extname returns ''
    expect(normalizeExtension('.gitignore')).toBe('')
  })

  it('handles filenames with multiple dots', () => {
    expect(normalizeExtension('my.archive.tar.gz')).toBe('.gz')
  })
})
