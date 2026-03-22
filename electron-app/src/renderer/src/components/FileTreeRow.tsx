import { memo } from 'react'
import type { TreeNode } from '@shared/types'
import { EMOJI_ICONS } from '@shared/icons'
import { ChevronDown, ChevronRight } from 'lucide-react'

interface FileTreeRowProps {
  node: TreeNode
  depth: number
  onRowClick: (id: string, shiftKey: boolean) => void
  onToggleExpand: (id: string) => void
  onPreview?: (id: string) => void
}

export const FileTreeRow = memo(function FileTreeRow({
  node,
  depth,
  onRowClick,
  onToggleExpand,
  onPreview
}: FileTreeRowProps) {
  const icon = EMOJI_ICONS[node.iconGroup] ?? EMOJI_ICONS.binary

  const bgClass = node.checked
    ? 'bg-blue-500/10 hover:bg-blue-500/20 border-l-blue-500'
    : 'hover:bg-slate-800/60 border-l-transparent'

  return (
    <div
      className={`flex items-center h-9 cursor-pointer select-none border-l-[3px] transition-colors ${bgClass}`}
      onClick={(e) => onRowClick(node.id, e.shiftKey)}
      onDoubleClick={() => {
        if (node.kind === 'file' && onPreview) onPreview(node.id)
      }}
    >
      {/* Indent spacer */}
      <div style={{ width: `${depth * 20 + 8}px` }} className="shrink-0" />

      {/* Chevron for folders (left of icon) */}
      {node.kind === 'folder' ? (
        <button
          className="flex items-center justify-center size-5 rounded hover:bg-slate-700/60 text-slate-500 hover:text-slate-300 shrink-0 mr-1 transition-colors"
          onClick={(e) => {
            e.stopPropagation()
            onToggleExpand(node.id)
          }}
          title={node.expanded ? 'Collapse' : 'Expand'}
        >
          {node.expanded ? (
            <ChevronDown className="size-3.5" />
          ) : (
            <ChevronRight className="size-3.5" />
          )}
        </button>
      ) : (
        <div className="size-5 mr-1 shrink-0" />
      )}

      {/* Icon */}
      <span className="text-base mr-2 shrink-0 leading-none">{icon}</span>

      {/* Name */}
      <span
        className={`text-[13px] truncate leading-tight ${
          node.kind === 'folder'
            ? 'font-semibold text-slate-100'
            : 'text-slate-300'
        }`}
      >
        {node.name}
      </span>

      {/* Spacer */}
      <div className="flex-1 min-w-3" />

      {/* Size for files */}
      {node.kind === 'file' && node.size && (
        <span className="text-[11px] text-slate-500 mr-3 shrink-0 tabular-nums">
          {node.size}
        </span>
      )}
    </div>
  )
})
