import { useRef, useEffect, useState, useCallback } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useFileTree } from '@/hooks/useFileTree'
import { useTaskStore } from '@/stores/task-store'
import { FileTreeRow } from './FileTreeRow'
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react'

interface MenuPos {
  x: number
  y: number
}

function SortButton({ label, sortKey: key }: { label: string; sortKey: 'name' | 'size' | 'type' }): JSX.Element {
  const currentKey = useTaskStore((s) => s.sortKey)
  const currentDir = useTaskStore((s) => s.sortDir)
  const setSort = useTaskStore((s) => s.setSort)
  const active = currentKey === key

  return (
    <button
      onClick={() => setSort(key)}
      className={`flex items-center gap-1 px-2 py-1 text-[11px] rounded transition-colors ${
        active
          ? 'text-blue-400 bg-blue-500/10'
          : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/60'
      }`}
      title={`Sort by ${label}`}
    >
      {label}
      {active ? (
        currentDir === 'asc' ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />
      ) : (
        <ArrowUpDown className="size-3 opacity-40" />
      )}
    </button>
  )
}

export function FileTree(): JSX.Element {
  const {
    visibleNodes,
    handleRowClick,
    toggleExpand,
    selectAll,
    deselectAll,
    expandAll,
    collapseAll
  } = useFileTree()

  const setPreviewNodeId = useTaskStore((s) => s.setPreviewNodeId)
  const handlePreview = useCallback((nodeId: string) => {
    setPreviewNodeId(nodeId)
  }, [setPreviewNodeId])

  const parentRef = useRef<HTMLDivElement>(null)
  const [menu, setMenu] = useState<MenuPos | null>(null)

  const rowVirtualizer = useVirtualizer({
    count: visibleNodes.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 36,
    overscan: 30
  })

  // Close menu on left click or scroll
  useEffect(() => {
    if (!menu) return
    const close = (): void => setMenu(null)
    window.addEventListener('click', close)
    window.addEventListener('scroll', close, true)
    return () => {
      window.removeEventListener('click', close)
      window.removeEventListener('scroll', close, true)
    }
  }, [menu])

  // Keyboard shortcut: Ctrl/Cmd+A to select all
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent): void => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'a') {
        const active = document.activeElement
        if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA')) return
        e.preventDefault()
        selectAll()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [selectAll])

  const menuAction = (fn: () => void): void => {
    fn()
    setMenu(null)
  }

  // Native DOM contextmenu event
  useEffect(() => {
    const el = parentRef.current
    if (!el) return
    const handler = (e: MouseEvent): void => {
      e.preventDefault()
      e.stopPropagation()
      setMenu({ x: e.clientX, y: e.clientY })
    }
    el.addEventListener('contextmenu', handler)
    return () => el.removeEventListener('contextmenu', handler)
  }, [])

  return (
    <>
      {/* Sort bar */}
      <div className="flex items-center gap-1 px-2 py-1 border-b border-slate-800 bg-slate-900/30 shrink-0">
        <span className="text-[11px] text-slate-600 mr-1">Sort:</span>
        <SortButton label="Name" sortKey="name" />
        <SortButton label="Size" sortKey="size" />
        <SortButton label="Type" sortKey="type" />
      </div>

      {/* Tree */}
      <div ref={parentRef} className="flex-1 overflow-auto">
        {visibleNodes.length === 0 ? (
          <div className="flex items-center justify-center h-full text-sm text-slate-500">
            No files to display
          </div>
        ) : (
          <div
            style={{
              height: `${rowVirtualizer.getTotalSize()}px`,
              width: '100%',
              position: 'relative'
            }}
          >
            {rowVirtualizer.getVirtualItems().map((virtualRow) => {
              const { node, depth } = visibleNodes[virtualRow.index]
              return (
                <div
                  key={node.id}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: `${virtualRow.size}px`,
                    transform: `translateY(${virtualRow.start}px)`
                  }}
                >
                  <FileTreeRow
                    node={node}
                    depth={depth}
                    onRowClick={handleRowClick}
                    onToggleExpand={toggleExpand}
                    onPreview={handlePreview}
                  />
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Context menu */}
      {menu && (
        <div
          className="fixed z-[9999] min-w-[160px] rounded-lg border border-slate-600 bg-slate-800 py-1 shadow-2xl"
          style={{ left: menu.x, top: menu.y }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            className="w-full text-left px-3 py-1.5 text-sm text-slate-100 hover:bg-blue-600 transition-colors"
            onMouseDown={() => menuAction(selectAll)}
          >
            Select All
          </button>
          <button
            className="w-full text-left px-3 py-1.5 text-sm text-slate-100 hover:bg-blue-600 transition-colors"
            onMouseDown={() => menuAction(deselectAll)}
          >
            Deselect All
          </button>
          <div className="my-1 h-px bg-slate-600 mx-1" />
          <button
            className="w-full text-left px-3 py-1.5 text-sm text-slate-100 hover:bg-blue-600 transition-colors"
            onMouseDown={() => menuAction(expandAll)}
          >
            Expand All
          </button>
          <button
            className="w-full text-left px-3 py-1.5 text-sm text-slate-100 hover:bg-blue-600 transition-colors"
            onMouseDown={() => menuAction(collapseAll)}
          >
            Collapse All
          </button>
        </div>
      )}
    </>
  )
}
