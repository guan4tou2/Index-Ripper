import { useCallback, useEffect, useRef } from 'react'
import { useTaskStore } from '@/stores/task-store'
import { useIpcEvent } from './useIpc'
import { toast } from 'sonner'
import type { Task, TreeNode } from '../../../shared/types'

/**
 * Subscribes to all IPC events from the main process and updates the Zustand store.
 * Batches scan:item events to avoid O(n²) store updates.
 * Should be called once at the App root level.
 */
export function useIpcListeners(): void {
  const updateTask = useTaskStore((s) => s.updateTask)
  const updateDownload = useTaskStore((s) => s.updateDownload)

  // --- Batch buffer for scan:item events ---
  const pendingNodes = useRef<Map<string, TreeNode[]>>(new Map())
  const flushScheduled = useRef(false)

  const flushNodes = useCallback(() => {
    flushScheduled.current = false
    const batches = pendingNodes.current
    if (batches.size === 0) return

    // Process all pending batches at once
    for (const [taskId, nodes] of batches) {
      const state = useTaskStore.getState()
      const task = state.tasks[taskId]
      if (!task) continue

      // Build updated nodes map in one pass (no per-node spread)
      const updatedNodes = { ...task.nodes }
      const updatedRoots = [...task.roots]

      for (const node of nodes) {
        const nodeToAdd = node.kind === 'folder' ? { ...node, expanded: true } : node
        updatedNodes[nodeToAdd.id] = nodeToAdd

        // Link to parent
        if (nodeToAdd.parentId && updatedNodes[nodeToAdd.parentId]) {
          const parent = updatedNodes[nodeToAdd.parentId]
          if (!parent.children.includes(nodeToAdd.id)) {
            updatedNodes[nodeToAdd.parentId] = {
              ...parent,
              children: [...parent.children, nodeToAdd.id]
            }
          }
        }

        // Track roots
        if (!nodeToAdd.parentId && !updatedRoots.includes(nodeToAdd.id)) {
          updatedRoots.push(nodeToAdd.id)
        }
      }

      useTaskStore.getState().updateTask(taskId, { nodes: updatedNodes, roots: updatedRoots })
    }

    batches.clear()
  }, [])

  const scheduleFlush = useCallback(() => {
    if (!flushScheduled.current) {
      flushScheduled.current = true
      requestAnimationFrame(flushNodes)
    }
  }, [flushNodes])

  // --- Scan events ---

  const onScanItem = useCallback(
    (...args: unknown[]) => {
      const [taskId, nodeData] = args as [string, TreeNode]
      const batch = pendingNodes.current.get(taskId) ?? []
      batch.push(nodeData)
      pendingNodes.current.set(taskId, batch)
      scheduleFlush()
    },
    [scheduleFlush]
  )

  const onScanProgress = useCallback(
    (...args: unknown[]) => {
      const [taskId, scanned, total] = args as [string, number, number]
      updateTask(taskId, { scanProgress: { scanned, total } })
    },
    [updateTask]
  )

  const onScanFinished = useCallback(
    (...args: unknown[]) => {
      // Flush any remaining nodes first
      flushNodes()

      const [taskId] = args as [string]
      const task = useTaskStore.getState().tasks[taskId]
      const status = task?.status === 'scanning' ? 'scanned' : 'cancelled'
      updateTask(taskId, { status })

      if (status === 'scanned' && task) {
        const fileCount = Object.values(task.nodes).filter((n) => n.kind === 'file').length
        toast.success(`Scan finished — ${fileCount} files found`)
      }
    },
    [updateTask, flushNodes]
  )

  const onScanError = useCallback((...args: unknown[]) => {
    const [_taskId, errUrl, message] = args as [string, string, string]
    const text = `[Error] ${errUrl}: ${message}`
    window.dispatchEvent(new CustomEvent('log-message', { detail: { text } }))
  }, [])

  // --- Download events ---

  const onDownloadProgress = useCallback(
    (...args: unknown[]) => {
      const [taskId, fileId, percent, speed] = args as [string, string, number, number]
      updateDownload(taskId, fileId, { progress: percent, speed, status: 'downloading' })
    },
    [updateDownload]
  )

  const onDownloadStatus = useCallback(
    (...args: unknown[]) => {
      const [taskId, fileId, status] = args as [string, string, string]
      updateDownload(taskId, fileId, {
        status: status as 'queued' | 'downloading' | 'paused' | 'completed' | 'failed' | 'cancelled'
      })
    },
    [updateDownload]
  )

  const onDownloadFinished = useCallback(
    (...args: unknown[]) => {
      const [taskId, completed, total] = args as [string, number, number]
      updateTask(taskId, { status: 'done' })
      toast.success(`Downloaded ${completed}/${total} files`)
    },
    [updateTask]
  )

  const onLogMessage = useCallback((...args: unknown[]) => {
    const [_taskId, text] = args as [string, string]
    window.dispatchEvent(new CustomEvent('log-message', { detail: { text } }))
  }, [])

  // --- Register all listeners ---

  useIpcEvent('scan:item', onScanItem)
  useIpcEvent('scan:progress', onScanProgress)
  useIpcEvent('scan:finished', onScanFinished)
  useIpcEvent('scan:error', onScanError)
  useIpcEvent('download:progress', onDownloadProgress)
  useIpcEvent('download:status', onDownloadStatus)
  useIpcEvent('download:finished', onDownloadFinished)
  useIpcEvent('log:message', onLogMessage)

  // Create a default task on mount if none exists
  useEffect(() => {
    const state = useTaskStore.getState()
    if (Object.keys(state.tasks).length === 0) {
      ;(window.api.task.create('') as Promise<Task>).then((task) => {
        useTaskStore.getState().createTask(task.id, task.url)
      })
    }
  }, [])
}
