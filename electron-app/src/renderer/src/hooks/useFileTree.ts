import { useMemo, useCallback, useRef } from 'react'
import { useTaskStore } from '@/stores/task-store'
import type { TreeNode } from '@shared/types'

export interface VisibleNode {
  node: TreeNode
  depth: number
}

export type SortKey = 'name' | 'size' | 'type' | 'none'
export type SortDir = 'asc' | 'desc'

function parseSizeBytes(size: string): number {
  if (!size || size === 'Unknown') return -1
  const match = size.match(/^([\d.]+)\s*(B|KB|MB|GB|TB)$/i)
  if (!match) return -1
  const val = parseFloat(match[1])
  const unit = match[2].toUpperCase()
  const multipliers: Record<string, number> = { B: 1, KB: 1024, MB: 1048576, GB: 1073741824, TB: 1099511627776 }
  return val * (multipliers[unit] ?? 1)
}

function sortChildren(
  children: string[],
  nodes: Record<string, TreeNode>,
  key: SortKey,
  dir: SortDir
): string[] {
  if (key === 'none' || children.length === 0) return children

  const sorted = [...children].sort((a, b) => {
    const na = nodes[a]
    const nb = nodes[b]
    if (!na || !nb) return 0

    // Folders always before files
    if (na.kind !== nb.kind) return na.kind === 'folder' ? -1 : 1

    let cmp = 0
    switch (key) {
      case 'name':
        cmp = na.name.localeCompare(nb.name, undefined, { numeric: true, sensitivity: 'base' })
        break
      case 'size':
        cmp = parseSizeBytes(na.size) - parseSizeBytes(nb.size)
        break
      case 'type': {
        const extA = na.name.lastIndexOf('.') >= 0 ? na.name.slice(na.name.lastIndexOf('.')) : ''
        const extB = nb.name.lastIndexOf('.') >= 0 ? nb.name.slice(nb.name.lastIndexOf('.')) : ''
        cmp = extA.localeCompare(extB)
        if (cmp === 0) cmp = na.name.localeCompare(nb.name, undefined, { numeric: true })
        break
      }
    }
    return dir === 'desc' ? -cmp : cmp
  })
  return sorted
}

function flattenTree(
  nodes: Record<string, TreeNode>,
  roots: string[],
  sortKey: SortKey,
  sortDir: SortDir
): VisibleNode[] {
  const result: VisibleNode[] = []
  function walk(nodeId: string, depth: number): void {
    const node = nodes[nodeId]
    if (!node || node.hidden) return
    result.push({ node, depth })
    if (node.kind === 'folder' && node.expanded) {
      const sorted = sortChildren(node.children, nodes, sortKey, sortDir)
      for (const childId of sorted) walk(childId, depth + 1)
    }
  }
  const sortedRoots = sortChildren(roots, nodes, sortKey, sortDir)
  for (const rootId of sortedRoots) walk(rootId, 0)
  return result
}

function updateFolderVisibility(nodes: Record<string, TreeNode>): void {
  const hasVisibleDescendant = (nodeId: string): boolean => {
    const node = nodes[nodeId]
    if (!node) return false
    if (node.kind === 'file') return !node.hidden
    return node.children.some((childId) => hasVisibleDescendant(childId))
  }
  for (const [id, node] of Object.entries(nodes)) {
    if (node.kind === 'folder') {
      nodes[id] = { ...node, hidden: !hasVisibleDescendant(id) }
    }
  }
}

export function useFileTree() {
  const activeTaskId = useTaskStore((s) => s.activeTaskId)
  const task = useTaskStore((s) => (s.activeTaskId ? s.tasks[s.activeTaskId] : null))
  const toggleCheckStore = useTaskStore((s) => s.toggleCheck)
  const toggleExpandStore = useTaskStore((s) => s.toggleExpand)
  const updateTask = useTaskStore((s) => s.updateTask)
  const sortKey = useTaskStore((s) => s.sortKey)
  const sortDir = useTaskStore((s) => s.sortDir)

  const nodes = task?.nodes ?? {}
  const roots = task?.roots ?? []

  // Track last clicked index for shift-select
  const lastClickedIndex = useRef<number>(-1)

  const visibleNodes = useMemo(
    () => flattenTree(nodes, roots, sortKey, sortDir),
    [nodes, roots, sortKey, sortDir]
  )

  const toggleCheck = useCallback(
    (nodeId: string) => {
      if (activeTaskId) toggleCheckStore(activeTaskId, nodeId)
    },
    [activeTaskId, toggleCheckStore]
  )

  /** Handle click with shift support for range selection. */
  const handleRowClick = useCallback(
    (nodeId: string, shiftKey: boolean) => {
      if (!activeTaskId) return

      // Read fresh state to avoid stale closures
      const currentTask = useTaskStore.getState().tasks[activeTaskId]
      if (!currentTask) return

      // Recompute visible list from fresh state
      const currentVisible = flattenTree(currentTask.nodes, currentTask.roots, sortKey, sortDir)
      const currentIndex = currentVisible.findIndex((v) => v.node.id === nodeId)
      if (currentIndex < 0) return

      if (shiftKey && lastClickedIndex.current >= 0) {
        const start = Math.min(lastClickedIndex.current, currentIndex)
        const end = Math.max(lastClickedIndex.current, currentIndex)

        const newNodes: Record<string, TreeNode> = {}
        for (const [id, node] of Object.entries(currentTask.nodes)) {
          newNodes[id] = { ...node }
        }

        for (let i = start; i <= end; i++) {
          const nid = currentVisible[i].node.id
          if (newNodes[nid]) {
            newNodes[nid] = { ...newNodes[nid], checked: true }
            if (newNodes[nid].kind === 'folder') {
              const cascade = (fid: string): void => {
                for (const cid of (newNodes[fid]?.children ?? [])) {
                  if (newNodes[cid]) {
                    newNodes[cid] = { ...newNodes[cid], checked: true }
                    if (newNodes[cid].kind === 'folder') cascade(cid)
                  }
                }
              }
              cascade(nid)
            }
          }
        }

        const checkedFiles = Object.values(newNodes)
          .filter((n) => n.kind === 'file' && n.checked)
          .map((n) => n.id)
        useTaskStore.getState().updateTask(activeTaskId, { nodes: newNodes, checkedFiles })
      } else {
        toggleCheckStore(activeTaskId, nodeId)
      }

      lastClickedIndex.current = currentIndex
    },
    [activeTaskId, sortKey, sortDir, toggleCheckStore]
  )

  const toggleExpand = useCallback(
    (nodeId: string) => {
      if (activeTaskId) toggleExpandStore(activeTaskId, nodeId)
    },
    [activeTaskId, toggleExpandStore]
  )

  const selectAll = useCallback(() => {
    if (!activeTaskId || !task) return
    const newNodes: Record<string, TreeNode> = {}
    for (const [id, node] of Object.entries(task.nodes)) {
      newNodes[id] = { ...node, checked: true }
    }
    const checkedFiles = Object.values(newNodes)
      .filter((n) => n.kind === 'file')
      .map((n) => n.id)
    updateTask(activeTaskId, { nodes: newNodes, checkedFiles })
  }, [activeTaskId, task, updateTask])

  const deselectAll = useCallback(() => {
    if (!activeTaskId || !task) return
    const newNodes: Record<string, TreeNode> = {}
    for (const [id, node] of Object.entries(task.nodes)) {
      newNodes[id] = { ...node, checked: false }
    }
    updateTask(activeTaskId, { nodes: newNodes, checkedFiles: [] })
  }, [activeTaskId, task, updateTask])

  const expandAll = useCallback(() => {
    if (!activeTaskId || !task) return
    const newNodes: Record<string, TreeNode> = {}
    for (const [id, node] of Object.entries(task.nodes)) {
      newNodes[id] = { ...node, expanded: node.kind === 'folder' ? true : node.expanded }
    }
    updateTask(activeTaskId, { nodes: newNodes })
  }, [activeTaskId, task, updateTask])

  const collapseAll = useCallback(() => {
    if (!activeTaskId || !task) return
    const newNodes: Record<string, TreeNode> = {}
    for (const [id, node] of Object.entries(task.nodes)) {
      newNodes[id] = { ...node, expanded: false }
    }
    updateTask(activeTaskId, { nodes: newNodes })
  }, [activeTaskId, task, updateTask])

  const searchFilter = useCallback(
    (query: string) => {
      if (!activeTaskId || !task) return
      const lowerQuery = query.toLowerCase()
      const newNodes: Record<string, TreeNode> = {}
      for (const [id, node] of Object.entries(task.nodes)) {
        if (!query) {
          newNodes[id] = { ...node, hidden: false }
        } else {
          const matches = node.name.toLowerCase().includes(lowerQuery)
          newNodes[id] = { ...node, hidden: !matches && node.kind !== 'folder' }
        }
      }
      if (query) {
        updateFolderVisibility(newNodes)
      }
      updateTask(activeTaskId, { nodes: newNodes })
    },
    [activeTaskId, task, updateTask]
  )

  const typeFilter = useCallback(
    (ext: string, visible: boolean) => {
      if (!activeTaskId) return
      const currentTask = useTaskStore.getState().tasks[activeTaskId]
      if (!currentTask) return

      const lowerExt = ext.toLowerCase()
      const newNodes: Record<string, TreeNode> = {}
      for (const [id, node] of Object.entries(currentTask.nodes)) {
        if (node.kind === 'file' && node.name.toLowerCase().endsWith(lowerExt)) {
          newNodes[id] = { ...node, hidden: !visible }
        } else {
          newNodes[id] = { ...node }
        }
      }
      updateFolderVisibility(newNodes)
      useTaskStore.getState().updateTask(activeTaskId, { nodes: newNodes })
    },
    [activeTaskId]
  )

  const setAllTypesVisible = useCallback(
    (visible: boolean) => {
      if (!activeTaskId) return
      const currentTask = useTaskStore.getState().tasks[activeTaskId]
      if (!currentTask) return

      const newNodes: Record<string, TreeNode> = {}
      for (const [id, node] of Object.entries(currentTask.nodes)) {
        if (node.kind === 'file') {
          newNodes[id] = { ...node, hidden: !visible }
        } else {
          newNodes[id] = { ...node }
        }
      }
      updateFolderVisibility(newNodes)
      useTaskStore.getState().updateTask(activeTaskId, { nodes: newNodes })
    },
    [activeTaskId]
  )

  const extensionCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const node of Object.values(nodes)) {
      if (node.kind === 'file') {
        const dotIndex = node.name.lastIndexOf('.')
        const ext = dotIndex >= 0 ? node.name.slice(dotIndex).toLowerCase() : '(no ext)'
        counts[ext] = (counts[ext] ?? 0) + 1
      }
    }
    return counts
  }, [nodes])

  const stats = useMemo(() => {
    let files = 0
    let folders = 0
    let selected = 0
    for (const node of Object.values(nodes)) {
      if (node.kind === 'file') {
        files++
        if (node.checked) selected++
      } else {
        folders++
      }
    }
    return { files, folders, selected }
  }, [nodes])

  return {
    visibleNodes,
    toggleCheck,
    handleRowClick,
    toggleExpand,
    selectAll,
    deselectAll,
    expandAll,
    collapseAll,
    searchFilter,
    typeFilter,
    setAllTypesVisible,
    extensionCounts,
    stats
  }
}
