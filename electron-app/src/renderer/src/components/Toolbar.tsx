import { useState } from 'react'
import { useTaskStore } from '@/stores/task-store'
import { Play, Square, Download, Pause, FolderOpen } from 'lucide-react'
import { toast } from 'sonner'
import type { Task } from '../../../shared/types'

const STATUS_CONFIG: Record<Task['status'], { color: string; label: string }> = {
  idle: { color: 'bg-slate-400', label: 'Ready' },
  scanning: { color: 'bg-yellow-400', label: 'Scanning' },
  scanned: { color: 'bg-green-400', label: 'Scanned' },
  downloading: { color: 'bg-blue-400', label: 'Downloading' },
  done: { color: 'bg-green-400', label: 'Done' },
  error: { color: 'bg-red-400', label: 'Error' },
  cancelled: { color: 'bg-orange-400', label: 'Cancelled' }
}

export function Toolbar(): JSX.Element {
  const activeTaskId = useTaskStore((s) => s.activeTaskId)
  const task = useTaskStore((s) => (s.activeTaskId ? s.tasks[s.activeTaskId] : null))
  const updateTask = useTaskStore((s) => s.updateTask)
  const [threadCount, setThreadCount] = useState(3)

  const url = task?.url ?? ''
  const status = task?.status ?? 'idle'
  const isScanning = status === 'scanning'
  const isDownloading = status === 'downloading'
  const showPause = isScanning || isDownloading
  const statusInfo = STATUS_CONFIG[status]

  const handleUrlChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    if (activeTaskId) {
      updateTask(activeTaskId, { url: e.target.value })
    }
  }

  const handleScanToggle = async (): Promise<void> => {
    if (!activeTaskId || !url) return

    if (isScanning) {
      await window.api.scan.stop(activeTaskId)
      updateTask(activeTaskId, { status: 'cancelled' })
    } else {
      // Clear previous scan data and start fresh
      updateTask(activeTaskId, {
        status: 'scanning',
        nodes: {},
        roots: [],
        checkedFiles: [],
        scanProgress: { scanned: 0, total: 0 }
      })
      // Fire-and-forget: results come back via IPC events
      window.api.scan.start(activeTaskId, url).catch((err: unknown) => {
        const message = err instanceof Error ? err.message : String(err)
        toast.error(`Scan failed: ${message}`)
        updateTask(activeTaskId, { status: 'error' })
      })
    }
  }

  const handleDownload = async (): Promise<void> => {
    if (!activeTaskId || !task) return

    // Determine download path
    let destPath = task.downloadPath
    if (!destPath) {
      const selected = await window.api.dialog.selectFolder()
      if (!selected) return // user cancelled
      destPath = selected
      updateTask(activeTaskId, { downloadPath: destPath })
    }

    // Build file list from checked files
    const files = task.checkedFiles
      .map((fileId) => {
        const node = task.nodes[fileId]
        if (!node || node.kind !== 'file') return null
        return {
          id: node.id,
          url: node.url,
          destPath,
          fileName: node.name
        }
      })
      .filter((f): f is NonNullable<typeof f> => f !== null)

    if (files.length === 0) {
      toast.error('No files selected for download')
      return
    }

    // Initialize download items in the store
    const downloads: Record<string, import('../../../shared/types').DownloadItem> = {}
    for (const file of files) {
      downloads[file.id] = {
        id: file.id,
        fileName: file.fileName,
        url: file.url,
        destPath: file.destPath,
        status: 'queued',
        progress: 0,
        speed: 0,
        totalSize: 0,
        downloadedSize: 0
      }
    }
    updateTask(activeTaskId, { status: 'downloading', downloads })

    try {
      await window.api.download.start(activeTaskId, files, destPath)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      toast.error(`Download failed: ${message}`)
      updateTask(activeTaskId, { status: 'error' })
    }
  }

  const handlePause = (): void => {
    if (!activeTaskId) return
    if (isScanning) {
      window.api.scan.pause(activeTaskId)
    } else if (isDownloading) {
      window.api.download.pause(activeTaskId)
    }
  }

  const handleThreadChange = (e: React.ChangeEvent<HTMLSelectElement>): void => {
    const count = Number(e.target.value)
    setThreadCount(count)
    window.api.download.setWorkers(count)
  }

  const handleSelectFolder = async (): Promise<void> => {
    if (!activeTaskId) return
    const selected = await window.api.dialog.selectFolder()
    if (selected) {
      updateTask(activeTaskId, { downloadPath: selected })
    }
  }

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-slate-900 border-b border-slate-800">
      {/* URL input */}
      <input
        type="text"
        value={url}
        onChange={handleUrlChange}
        placeholder="Enter URL to scan..."
        className="flex-1 min-w-0 h-8 px-3 rounded bg-slate-800 border border-slate-700 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
        onKeyDown={(e) => {
          if (e.key === 'Enter') handleScanToggle()
        }}
      />

      {/* Scan / Stop button */}
      <button
        onClick={handleScanToggle}
        disabled={!activeTaskId || !url}
        className="flex items-center gap-1.5 h-8 px-3 rounded text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {isScanning ? <Square className="size-3.5" /> : <Play className="size-3.5" />}
        {isScanning ? 'Stop' : 'Scan'}
      </button>

      {/* Download button */}
      <button
        onClick={handleDownload}
        disabled={!activeTaskId || !task?.checkedFiles.length}
        className="flex items-center justify-center h-8 w-8 rounded bg-slate-700 hover:bg-slate-600 text-slate-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        title="Download selected files"
      >
        <Download className="size-3.5" />
      </button>

      {/* Pause button */}
      {showPause && (
        <button
          onClick={handlePause}
          className="flex items-center justify-center h-8 w-8 rounded bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors"
          title="Pause"
        >
          <Pause className="size-3.5" />
        </button>
      )}

      {/* Folder button */}
      <button
        onClick={handleSelectFolder}
        disabled={!activeTaskId}
        className="flex items-center justify-center h-8 w-8 rounded bg-slate-700 hover:bg-slate-600 text-slate-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        title={task?.downloadPath || 'Select download folder'}
      >
        <FolderOpen className="size-3.5" />
      </button>

      {/* Thread count */}
      <select
        value={threadCount}
        onChange={handleThreadChange}
        className="h-8 px-2 rounded bg-slate-800 border border-slate-700 text-sm text-slate-300 focus:outline-none focus:border-blue-500 cursor-pointer"
        title="Thread count"
      >
        {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
          <option key={n} value={n}>
            {n}T
          </option>
        ))}
      </select>

      {/* Status indicator */}
      <div className="flex items-center gap-1.5 text-sm text-slate-400 ml-1 shrink-0">
        <span className={`inline-block size-2 rounded-full ${statusInfo.color}`} />
        {statusInfo.label}
      </div>
    </div>
  )
}
