// Pure implementation to avoid Node.js 'path' in browser context
function extname(filename: string): string {
  const dot = filename.lastIndexOf('.')
  return dot > 0 && dot < filename.length - 1 ? filename.slice(dot) : ''
}

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
