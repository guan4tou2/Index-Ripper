import { useTaskStore } from '../stores/task-store'
import { DownloadCard } from './DownloadCard'
import { Progress } from './ui/progress'
import type { DownloadItem } from '../../../shared/types'

function estimateTimeRemaining(items: DownloadItem[]): string | null {
  const downloading = items.filter((d) => d.status === 'downloading' && d.speed > 0)
  if (downloading.length === 0) return null

  const totalRemaining = downloading.reduce((acc, d) => {
    const remaining = d.totalSize > 0 ? d.totalSize - d.downloadedSize : 0
    return acc + remaining
  }, 0)

  const totalSpeed = downloading.reduce((acc, d) => acc + d.speed, 0)
  if (totalSpeed === 0 || totalRemaining === 0) return null

  const secsRemaining = totalRemaining / totalSpeed
  if (secsRemaining >= 3600) {
    return `~${Math.ceil(secsRemaining / 3600)} hr remaining`
  }
  if (secsRemaining >= 60) {
    return `~${Math.ceil(secsRemaining / 60)} min remaining`
  }
  return `~${Math.ceil(secsRemaining)} sec remaining`
}

export function DownloadsList(): JSX.Element {
  const activeTaskId = useTaskStore((s) => s.activeTaskId)
  const tasks = useTaskStore((s) => s.tasks)
  const updateDownload = useTaskStore((s) => s.updateDownload)

  const activeTask = activeTaskId ? tasks[activeTaskId] : null
  const downloads: DownloadItem[] = activeTask ? Object.values(activeTask.downloads) : []

  const completedCount = downloads.filter((d) => d.status === 'completed').length
  const total = downloads.length

  const aggregateProgress =
    total === 0
      ? 0
      : downloads.reduce((acc, d) => acc + d.progress, 0) / total

  const timeRemaining = estimateTimeRemaining(downloads)

  const handleCancel = (id: string): void => {
    if (!activeTaskId) return
    updateDownload(activeTaskId, id, { status: 'cancelled' })
    window.api.download.cancel(activeTaskId, id)
  }

  const handleRetry = (id: string): void => {
    if (!activeTaskId) return
    updateDownload(activeTaskId, id, { status: 'queued', progress: 0 })
    window.api.download.retry(activeTaskId, id)
  }

  if (downloads.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-slate-500 text-sm">
        No downloads yet
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {downloads.map((item) => (
          <DownloadCard
            key={item.id}
            item={item}
            onCancel={handleCancel}
            onRetry={handleRetry}
          />
        ))}
      </div>

      <div className="px-3 pb-3 pt-2 border-t border-slate-800 space-y-1.5">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>
            {completedCount}/{total} done
            {timeRemaining ? ` — ${timeRemaining}` : ''}
          </span>
          <span>{Math.round(aggregateProgress)}%</span>
        </div>
        <Progress value={aggregateProgress} className="h-1.5 bg-slate-800" />
      </div>
    </div>
  )
}
