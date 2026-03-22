import type { DownloadItem } from '../../../shared/types'
import { Progress } from './ui/progress'

interface DownloadCardProps {
  item: DownloadItem
  onCancel: (id: string) => void
  onRetry: (id: string) => void
}

const statusColors: Record<DownloadItem['status'], string> = {
  queued: 'text-slate-400',
  downloading: 'text-blue-400',
  paused: 'text-slate-400',
  completed: 'text-emerald-400',
  failed: 'text-red-400',
  cancelled: 'text-yellow-400'
}

const statusLabels: Record<DownloadItem['status'], string> = {
  queued: 'Queued',
  downloading: 'Downloading',
  paused: 'Paused',
  completed: 'Done',
  failed: 'Failed',
  cancelled: 'Cancelled'
}

function formatSpeed(bytesPerSec: number): string {
  if (bytesPerSec >= 1024 * 1024) {
    return `${(bytesPerSec / (1024 * 1024)).toFixed(1)} MB/s`
  }
  if (bytesPerSec >= 1024) {
    return `${(bytesPerSec / 1024).toFixed(1)} KB/s`
  }
  return `${bytesPerSec} B/s`
}

export function DownloadCard({ item, onCancel, onRetry }: DownloadCardProps): JSX.Element {
  const showCancel = item.status === 'queued' || item.status === 'downloading' || item.status === 'paused'
  const showRetry = item.status === 'failed'
  const colorClass = statusColors[item.status]

  return (
    <div className="bg-slate-900 rounded-lg border border-slate-800 p-3 flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-slate-100 text-sm truncate flex-1" title={item.fileName}>
          {item.fileName}
        </span>
        <div className="flex items-center gap-2 shrink-0">
          {item.status === 'downloading' && item.speed > 0 && (
            <span className="text-slate-400 text-xs">{formatSpeed(item.speed)}</span>
          )}
          <span className={`text-xs font-medium ${colorClass}`}>{statusLabels[item.status]}</span>
        </div>
      </div>

      <Progress
        value={item.progress}
        className="h-1.5 bg-slate-800"
      />

      {(showCancel || showRetry) && (
        <div className="flex justify-end gap-2">
          {showCancel && (
            <button
              onClick={() => onCancel(item.id)}
              className="text-xs text-slate-400 hover:text-slate-200 px-2 py-0.5 rounded border border-slate-700 hover:border-slate-500 transition-colors"
            >
              Cancel
            </button>
          )}
          {showRetry && (
            <button
              onClick={() => onRetry(item.id)}
              className="text-xs text-blue-400 hover:text-blue-200 px-2 py-0.5 rounded border border-blue-700 hover:border-blue-500 transition-colors"
            >
              Retry
            </button>
          )}
        </div>
      )}
    </div>
  )
}
