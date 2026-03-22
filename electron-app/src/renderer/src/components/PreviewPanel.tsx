import { useEffect, useState } from 'react'
import { useTaskStore } from '@/stores/task-store'
import { Eye, FileText, Image, X } from 'lucide-react'

const IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.ico']
const TEXT_EXTS = [
  '.txt', '.md', '.html', '.htm', '.css', '.js', '.ts', '.tsx', '.jsx',
  '.json', '.yaml', '.yml', '.toml', '.xml', '.py', '.go', '.rs', '.java',
  '.c', '.cpp', '.h', '.sh', '.bat', '.log', '.csv', '.ini', '.cfg',
  '.env', '.gitignore', '.dockerfile', '.makefile',
]

function getExt(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot).toLowerCase() : ''
}

function isImage(name: string): boolean {
  return IMAGE_EXTS.includes(getExt(name))
}

function isText(name: string): boolean {
  const ext = getExt(name)
  return TEXT_EXTS.includes(ext) || ext === ''
}

export function PreviewPanel(): JSX.Element {
  const previewNodeId = useTaskStore((s) => s.previewNodeId)
  const setPreviewNodeId = useTaskStore((s) => s.setPreviewNodeId)
  const task = useTaskStore((s) => (s.activeTaskId ? s.tasks[s.activeTaskId] : null))

  const node = previewNodeId && task ? task.nodes[previewNodeId] : null

  const [imageDataUrl, setImageDataUrl] = useState<string | null>(null)
  const [textContent, setTextContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setImageDataUrl(null)
    setTextContent(null)
    setError(null)

    if (!node || node.kind !== 'file' || !node.url) return

    let cancelled = false
    setLoading(true)

    if (isImage(node.name)) {
      // Fetch image via main process IPC
      ;(window.api.preview.fetch(node.url) as Promise<{ dataUrl: string }>)
        .then(({ dataUrl }) => {
          if (!cancelled) setImageDataUrl(dataUrl)
        })
        .catch((err: Error) => {
          if (!cancelled) setError(err.message)
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    } else if (isText(node.name)) {
      // Fetch text via main process IPC
      ;(window.api.preview.fetchText(node.url) as Promise<string>)
        .then((text) => {
          if (!cancelled) setTextContent(text)
        })
        .catch((err: Error) => {
          if (!cancelled) setError(err.message)
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    } else {
      setLoading(false)
    }

    return () => { cancelled = true }
  }, [node?.id, node?.url])

  if (!node) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-2">
        <Eye className="size-8 opacity-30" />
        <p className="text-sm">Double-click a file to preview</p>
      </div>
    )
  }

  const ext = getExt(node.name)

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-slate-800 bg-slate-900/50 shrink-0">
        {isImage(node.name) ? (
          <Image className="size-4 text-blue-400 shrink-0" />
        ) : (
          <FileText className="size-4 text-blue-400 shrink-0" />
        )}
        <span className="text-sm text-slate-200 truncate flex-1">{node.name}</span>
        <span className="text-[11px] text-slate-500 shrink-0">{node.size}</span>
        <button
          onClick={() => setPreviewNodeId(null)}
          className="flex items-center justify-center size-5 rounded-full hover:bg-slate-700 text-slate-500 hover:text-slate-300 shrink-0 transition-colors"
          title="Close preview"
        >
          <X className="size-3" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-3">
        {loading && (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-slate-500">Loading preview...</p>
          </div>
        )}

        {error && !loading && (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        {!loading && !error && isImage(node.name) && imageDataUrl && (
          <div className="flex items-center justify-center h-full">
            <img
              src={imageDataUrl}
              alt={node.name}
              className="max-w-full max-h-full object-contain rounded-lg"
            />
          </div>
        )}

        {!loading && !error && isText(node.name) && textContent !== null && (
          <pre className="text-[12px] leading-relaxed text-slate-300 font-mono whitespace-pre-wrap break-all">
            {textContent}
          </pre>
        )}

        {!loading && !error && !isImage(node.name) && !isText(node.name) && (
          <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-2">
            <Eye className="size-8 opacity-30" />
            <p className="text-sm">Preview not available for {ext || 'this file type'}</p>
            <p className="text-xs text-slate-600">Supports: images and text files</p>
          </div>
        )}
      </div>
    </div>
  )
}
