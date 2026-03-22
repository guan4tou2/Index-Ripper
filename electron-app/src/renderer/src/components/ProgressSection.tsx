import { useTaskStore } from '@/stores/task-store'

export function ProgressSection(): JSX.Element | null {
  const task = useTaskStore((s) => (s.activeTaskId ? s.tasks[s.activeTaskId] : null))

  if (!task) return null

  const isScanning = task.status === 'scanning'
  const isDownloading = task.status === 'downloading'

  if (!isScanning && !isDownloading) return null

  // Scan progress
  if (isScanning) {
    const { scanned, total } = task.scanProgress
    const indeterminate = total === 0
    const pct = total > 0 ? (scanned / total) * 100 : 0

    return (
      <div className="px-3 py-1.5 bg-slate-900 border-b border-slate-800">
        <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
          {indeterminate ? (
            <div className="h-full bg-blue-500 rounded-full animate-indeterminate" />
          ) : (
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-300"
              style={{ width: `${pct}%` }}
            />
          )}
        </div>
        <div className="text-xs text-slate-400 mt-1">
          {indeterminate
            ? `Discovering URLs… ${scanned > 0 ? `${scanned} found` : ''}`
            : `Scanning… ${scanned}/${total} (${pct.toFixed(0)}%)`}
        </div>
        <style>{`
          @keyframes indeterminate {
            0% { transform: translateX(-100%); width: 40%; }
            50% { transform: translateX(100%); width: 60%; }
            100% { transform: translateX(300%); width: 40%; }
          }
          .animate-indeterminate {
            animation: indeterminate 1.5s ease-in-out infinite;
            width: 40%;
          }
        `}</style>
      </div>
    )
  }

  // Download progress
  const downloads = Object.values(task.downloads)
  if (downloads.length === 0) return null

  const completed = downloads.filter((d) => d.status === 'completed').length
  const total = downloads.length
  const pct = total > 0 ? (completed / total) * 100 : 0

  // Aggregate speed
  const activeSpeed = downloads
    .filter((d) => d.status === 'downloading')
    .reduce((sum, d) => sum + d.speed, 0)

  const formatSpeed = (bytesPerSec: number): string => {
    if (bytesPerSec < 1024) return `${bytesPerSec.toFixed(0)} B/s`
    if (bytesPerSec < 1024 * 1024) return `${(bytesPerSec / 1024).toFixed(1)} KB/s`
    return `${(bytesPerSec / (1024 * 1024)).toFixed(1)} MB/s`
  }

  return (
    <div className="px-3 py-1.5 bg-slate-900 border-b border-slate-800">
      <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-emerald-500 rounded-full transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-slate-400 mt-1">
        <span>
          Downloaded {completed}/{total} ({pct.toFixed(0)}%)
        </span>
        {activeSpeed > 0 && <span>{formatSpeed(activeSpeed)}</span>}
      </div>
    </div>
  )
}
