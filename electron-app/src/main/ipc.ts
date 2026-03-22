import { ipcMain, dialog, BrowserWindow } from 'electron'
import type { TaskQueue } from './task-queue'

// electron-store v10 is ESM-only; use dynamic import for CJS compat.
interface StoreInstance {
  store: Record<string, unknown>
  get(key: string): unknown
  set(key: string, value: unknown): void
}

let storeInstance: StoreInstance | null = null

async function getStore(): Promise<StoreInstance> {
  if (storeInstance) return storeInstance
  const { default: Store } = await import('electron-store')
  storeInstance = new Store() as unknown as StoreInstance
  return storeInstance
}

export function registerIpcHandlers(
  taskQueue: TaskQueue,
  mainWindow: BrowserWindow
): void {
  const send = (channel: string, ...args: unknown[]): void => {
    if (!mainWindow.isDestroyed()) {
      mainWindow.webContents.send(channel, ...args)
    }
  }

  // -------------------------------------------------------------------------
  // Task management
  // -------------------------------------------------------------------------

  ipcMain.handle('task:create', (_event, url: string) => {
    const task = taskQueue.createTask(url)
    return task
  })

  ipcMain.handle('task:remove', (_event, taskId: string) => {
    taskQueue.removeTask(taskId)
  })

  // -------------------------------------------------------------------------
  // Scan
  // -------------------------------------------------------------------------

  ipcMain.handle('scan:start', (_event, taskId: string, url: string) => {
    const entry = taskQueue.getTask(taskId)
    if (!entry) throw new Error(`Unknown task: ${taskId}`)

    entry.task.status = 'scanning'

    // Fire-and-forget: don't await — let scan run in background
    // Results are streamed via IPC events
    entry.scanner.scan(url, {
      onItem: (node, parentId) => {
        send('scan:item', taskId, node, parentId)
      },
      onProgress: (scanned, total) => {
        entry.task.scanProgress = { scanned, total }
        send('scan:progress', taskId, scanned, total)
      },
      onError: (errUrl, err) => {
        send('scan:error', taskId, errUrl, err.message)
      },
      onFinished: () => {
        if (entry.task.status === 'scanning') {
          entry.task.status = 'scanned'
        }
        send('scan:finished', taskId)
      }
    }).catch((err) => {
      send('scan:error', taskId, url, String(err))
      send('scan:finished', taskId)
    })
  })

  ipcMain.handle('scan:stop', (_event, taskId: string) => {
    const entry = taskQueue.getTask(taskId)
    if (!entry) throw new Error(`Unknown task: ${taskId}`)
    entry.scanner.abort()
    entry.task.status = 'cancelled'
  })

  ipcMain.handle('scan:pause', (_event, taskId: string) => {
    const entry = taskQueue.getTask(taskId)
    if (!entry) throw new Error(`Unknown task: ${taskId}`)
    entry.scanner.pause()
  })

  ipcMain.handle('scan:resume', (_event, taskId: string) => {
    const entry = taskQueue.getTask(taskId)
    if (!entry) throw new Error(`Unknown task: ${taskId}`)
    entry.scanner.resume()
  })

  // -------------------------------------------------------------------------
  // Download
  // -------------------------------------------------------------------------

  ipcMain.handle(
    'download:start',
    async (
      _event,
      taskId: string,
      files: Array<{ id: string; url: string; destPath: string; fileName: string }>,
      _destPath: string
    ) => {
      const entry = taskQueue.getTask(taskId)
      if (!entry) throw new Error(`Unknown task: ${taskId}`)

      entry.task.status = 'downloading'

      await entry.downloader.downloadFiles(files, {
        onProgress: (fileId, percent, speed) => {
          send('download:progress', taskId, fileId, percent, speed)
        },
        onStatus: (fileId, status) => {
          send('download:status', taskId, fileId, status)
        },
        onLog: (message) => {
          send('log:message', taskId, message)
        },
        onFinished: (completed, total) => {
          entry.task.status = 'done'
          send('download:finished', taskId, completed, total)
        }
      })
    }
  )

  ipcMain.handle('download:pause', (_event, taskId: string) => {
    const entry = taskQueue.getTask(taskId)
    if (!entry) throw new Error(`Unknown task: ${taskId}`)
    entry.downloader.pause()
  })

  ipcMain.handle('download:resume', (_event, taskId: string) => {
    const entry = taskQueue.getTask(taskId)
    if (!entry) throw new Error(`Unknown task: ${taskId}`)
    entry.downloader.resume()
  })

  ipcMain.handle('download:cancel', (_event, taskId: string, fileId: string) => {
    const entry = taskQueue.getTask(taskId)
    if (!entry) throw new Error(`Unknown task: ${taskId}`)
    entry.downloader.cancelFile(fileId)
  })

  ipcMain.handle('download:cancelAll', (_event, taskId: string) => {
    const entry = taskQueue.getTask(taskId)
    if (!entry) throw new Error(`Unknown task: ${taskId}`)
    entry.downloader.cancelAll()
  })

  ipcMain.handle('download:retry', async (_event, taskId: string, fileId: string) => {
    const entry = taskQueue.getTask(taskId)
    if (!entry) throw new Error(`Unknown task: ${taskId}`)

    // Find the download item info from the task
    const downloadItem = entry.task.downloads[fileId]
    if (!downloadItem) throw new Error(`Unknown download: ${fileId}`)

    await entry.downloader.downloadOne(
      {
        id: downloadItem.id,
        url: downloadItem.url,
        destPath: downloadItem.destPath,
        fileName: downloadItem.fileName
      },
      {
        onProgress: (fId, percent, speed) => {
          send('download:progress', taskId, fId, percent, speed)
        },
        onStatus: (fId, status) => {
          send('download:status', taskId, fId, status)
        },
        onLog: (message) => {
          send('log:message', taskId, message)
        }
      },
      1
    )
  })

  ipcMain.handle('download:setWorkers', async (_event, count: number) => {
    for (const entry of taskQueue.tasks.values()) {
      await entry.downloader.setConcurrency(count)
    }
  })

  // -------------------------------------------------------------------------
  // Settings (electron-store)
  // -------------------------------------------------------------------------

  ipcMain.handle('settings:get', async () => {
    const store = await getStore()
    return store.store
  })

  ipcMain.handle('settings:set', async (_event, data: Record<string, unknown>) => {
    const store = await getStore()
    for (const [key, value] of Object.entries(data)) {
      store.set(key, value)
    }
  })

  // -------------------------------------------------------------------------
  // Dialog
  // -------------------------------------------------------------------------

  ipcMain.handle('dialog:selectFolder', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory']
    })
    if (result.canceled || result.filePaths.length === 0) {
      return null
    }
    return result.filePaths[0]
  })

  // -------------------------------------------------------------------------
  // Preview — fetch file content from remote URL via main process
  // -------------------------------------------------------------------------

  ipcMain.handle('preview:fetch', async (_event, url: string) => {
    const response = await globalThis.fetch(url)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const contentType = response.headers.get('content-type') ?? ''
    const buffer = Buffer.from(await response.arrayBuffer())
    const base64 = buffer.toString('base64')
    return { dataUrl: `data:${contentType};base64,${base64}`, contentType }
  })

  ipcMain.handle('preview:fetchText', async (_event, url: string) => {
    const response = await globalThis.fetch(url)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const text = await response.text()
    return text.slice(0, 200 * 1024) // 200KB limit
  })
}
