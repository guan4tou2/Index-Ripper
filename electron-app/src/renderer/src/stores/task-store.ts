import { create } from 'zustand'
import type { Task, TreeNode, DownloadItem } from '../../../shared/types'

function createEmptyTask(id: string, url: string): Task {
  return {
    id,
    url,
    status: 'idle',
    nodes: {},
    roots: [],
    checkedFiles: [],
    downloads: {},
    scanProgress: { scanned: 0, total: 0 },
    downloadPath: ''
  }
}

type SortKey = 'name' | 'size' | 'type' | 'none'
type SortDir = 'asc' | 'desc'

interface TaskStore {
  tasks: Record<string, Task>
  activeTaskId: string | null
  previewNodeId: string | null
  sortKey: SortKey
  sortDir: SortDir

  // Preview & Sort
  setPreviewNodeId: (nodeId: string | null) => void
  setSort: (key: SortKey) => void

  // Task management
  createTask: (id: string, url: string) => void
  removeTask: (taskId: string) => void
  setActiveTask: (taskId: string) => void
  updateTask: (taskId: string, partial: Partial<Task>) => void

  // Tree operations
  getNodes: (taskId: string) => Record<string, TreeNode>
  addNode: (taskId: string, node: TreeNode) => void
  toggleCheck: (taskId: string, nodeId: string) => void
  toggleExpand: (taskId: string, nodeId: string) => void
  setHidden: (taskId: string, nodeId: string, hidden: boolean) => void

  // Download operations
  updateDownload: (taskId: string, downloadId: string, partial: Partial<DownloadItem>) => void
  setDownloads: (taskId: string, downloads: Record<string, DownloadItem>) => void
}

function cascadeCheck(nodes: Record<string, TreeNode>, nodeId: string, checked: boolean): void {
  const node = nodes[nodeId]
  if (!node) return
  node.checked = checked
  for (const childId of node.children) {
    cascadeCheck(nodes, childId, checked)
  }
}

export const useTaskStore = create<TaskStore>((set, get) => ({
  tasks: {},
  activeTaskId: null,
  previewNodeId: null,
  sortKey: 'name' as SortKey,
  sortDir: 'asc' as SortDir,

  setPreviewNodeId: (nodeId) => set({ previewNodeId: nodeId }),
  setSort: (key) => set((state) => ({
    sortKey: key,
    sortDir: state.sortKey === key && state.sortDir === 'asc' ? 'desc' : 'asc',
  })),

  createTask: (id, url) => {
    set((state) => ({
      tasks: { ...state.tasks, [id]: createEmptyTask(id, url) },
      activeTaskId: id
    }))
  },

  removeTask: (taskId) => {
    set((state) => {
      const { [taskId]: _, ...remaining } = state.tasks
      const ids = Object.keys(remaining)
      const newActive =
        state.activeTaskId === taskId ? (ids.length > 0 ? ids[ids.length - 1] : null) : state.activeTaskId
      return { tasks: remaining, activeTaskId: newActive }
    })
  },

  setActiveTask: (taskId) => {
    set({ activeTaskId: taskId })
  },

  updateTask: (taskId, partial) => {
    set((state) => {
      const task = state.tasks[taskId]
      if (!task) return state
      return {
        tasks: { ...state.tasks, [taskId]: { ...task, ...partial } }
      }
    })
  },

  getNodes: (taskId) => {
    const task = get().tasks[taskId]
    return task ? task.nodes : {}
  },

  addNode: (taskId, node) => {
    set((state) => {
      const task = state.tasks[taskId]
      if (!task) return state

      // Folders should be expanded by default so the tree is visible
      const nodeToAdd = node.kind === 'folder' ? { ...node, expanded: true } : node

      const updatedNodes = { ...task.nodes, [nodeToAdd.id]: nodeToAdd }

      // Add to parent's children array if it has a parent
      if (nodeToAdd.parentId && updatedNodes[nodeToAdd.parentId]) {
        const parent = updatedNodes[nodeToAdd.parentId]
        if (!parent.children.includes(nodeToAdd.id)) {
          updatedNodes[nodeToAdd.parentId] = {
            ...parent,
            children: [...parent.children, nodeToAdd.id]
          }
        }
      }

      const updatedRoots = nodeToAdd.parentId === '' && !task.roots.includes(nodeToAdd.id)
        ? [...task.roots, nodeToAdd.id]
        : task.roots

      return {
        tasks: {
          ...state.tasks,
          [taskId]: { ...task, nodes: updatedNodes, roots: updatedRoots }
        }
      }
    })
  },

  toggleCheck: (taskId, nodeId) => {
    set((state) => {
      const task = state.tasks[taskId]
      if (!task) return state
      const node = task.nodes[nodeId]
      if (!node) return state

      const newNodes = { ...task.nodes }
      // Deep copy nodes that will be modified
      for (const id of Object.keys(newNodes)) {
        newNodes[id] = { ...newNodes[id] }
      }
      cascadeCheck(newNodes, nodeId, !node.checked)

      // Recalculate checkedFiles
      const checkedFiles = Object.values(newNodes)
        .filter((n) => n.kind === 'file' && n.checked)
        .map((n) => n.id)

      return {
        tasks: {
          ...state.tasks,
          [taskId]: { ...task, nodes: newNodes, checkedFiles }
        }
      }
    })
  },

  toggleExpand: (taskId, nodeId) => {
    set((state) => {
      const task = state.tasks[taskId]
      if (!task) return state
      const node = task.nodes[nodeId]
      if (!node) return state
      return {
        tasks: {
          ...state.tasks,
          [taskId]: {
            ...task,
            nodes: { ...task.nodes, [nodeId]: { ...node, expanded: !node.expanded } }
          }
        }
      }
    })
  },

  setHidden: (taskId, nodeId, hidden) => {
    set((state) => {
      const task = state.tasks[taskId]
      if (!task) return state
      const node = task.nodes[nodeId]
      if (!node) return state
      return {
        tasks: {
          ...state.tasks,
          [taskId]: {
            ...task,
            nodes: { ...task.nodes, [nodeId]: { ...node, hidden } }
          }
        }
      }
    })
  },

  updateDownload: (taskId, downloadId, partial) => {
    set((state) => {
      const task = state.tasks[taskId]
      if (!task) return state
      const existing = task.downloads[downloadId] ?? ({} as DownloadItem)
      return {
        tasks: {
          ...state.tasks,
          [taskId]: {
            ...task,
            downloads: { ...task.downloads, [downloadId]: { ...existing, ...partial } }
          }
        }
      }
    })
  },

  setDownloads: (taskId, downloads) => {
    set((state) => {
      const task = state.tasks[taskId]
      if (!task) return state
      return {
        tasks: { ...state.tasks, [taskId]: { ...task, downloads } }
      }
    })
  }
}))
