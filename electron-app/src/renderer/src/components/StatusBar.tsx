import { useFileTree } from '@/hooks/useFileTree'
import { Files, Folder, CheckSquare } from 'lucide-react'

export function StatusBar(): JSX.Element {
  const { stats } = useFileTree()

  return (
    <div className="flex items-center gap-3 px-3 py-1.5 border-t border-slate-800 text-[11px] text-slate-500 shrink-0 bg-slate-900/50">
      <span className="flex items-center gap-1">
        <Files className="size-3" />
        {stats.files} files
      </span>
      <span className="flex items-center gap-1">
        <Folder className="size-3" />
        {stats.folders} folders
      </span>
      {stats.selected > 0 && (
        <span className="flex items-center gap-1 text-blue-400">
          <CheckSquare className="size-3" />
          {stats.selected} selected
        </span>
      )}
    </div>
  )
}
