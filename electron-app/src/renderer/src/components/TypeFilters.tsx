import { useState, useCallback } from 'react'
import { useFileTree } from '@/hooks/useFileTree'
import { Check, X } from 'lucide-react'

export function TypeFilters(): JSX.Element {
  const { extensionCounts, typeFilter, setAllTypesVisible } = useFileTree()
  const [hiddenExts, setHiddenExts] = useState<Set<string>>(new Set())

  const extensions = Object.entries(extensionCounts).sort(([a], [b]) => a.localeCompare(b))

  const toggleExt = useCallback(
    (ext: string) => {
      setHiddenExts((prev) => {
        const next = new Set(prev)
        if (next.has(ext)) {
          next.delete(ext)
          typeFilter(ext, true)
        } else {
          next.add(ext)
          typeFilter(ext, false)
        }
        return next
      })
    },
    [typeFilter]
  )

  const showAll = useCallback(() => {
    setAllTypesVisible(true)
    setHiddenExts(new Set())
  }, [setAllTypesVisible])

  const hideAll = useCallback(() => {
    setAllTypesVisible(false)
    setHiddenExts(new Set(Object.keys(extensionCounts)))
  }, [setAllTypesVisible, extensionCounts])

  if (extensions.length === 0) return <></>

  return (
    <div className="flex items-center border-b border-slate-800 bg-slate-900/30 shrink-0">
      {/* Fixed ALL buttons */}
      <div className="flex items-center gap-1 px-2 py-2 shrink-0 border-r border-slate-800">
        <button
          onClick={showAll}
          className="flex items-center gap-0.5 px-2 py-1.5 text-xs rounded-md bg-emerald-900/40 hover:bg-emerald-900/60 text-emerald-400 border border-emerald-800/50 transition-colors"
          title="Show all types"
        >
          <Check className="size-3" />
          All
        </button>
        <button
          onClick={hideAll}
          className="flex items-center gap-0.5 px-2 py-1.5 text-xs rounded-md bg-red-900/30 hover:bg-red-900/50 text-red-400 border border-red-800/40 transition-colors"
          title="Hide all types"
        >
          <X className="size-3" />
          All
        </button>
      </div>

      {/* Scrollable extension chips */}
      <div className="flex items-center gap-1 px-2 py-2 overflow-x-auto scrollbar-thin flex-1">
        {extensions.map(([ext, count]) => {
          const isHidden = hiddenExts.has(ext)
          return (
            <button
              key={ext}
              onClick={() => toggleExt(ext)}
              className={`shrink-0 px-2 py-1.5 text-xs rounded-md border transition-colors ${
                isHidden
                  ? 'bg-slate-900/50 text-slate-600 border-slate-800/50 line-through decoration-slate-600'
                  : 'bg-slate-800/80 text-slate-300 border-slate-700/50 hover:bg-slate-700/80 hover:text-slate-200'
              }`}
            >
              {ext} <span className="text-slate-500">{count}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
