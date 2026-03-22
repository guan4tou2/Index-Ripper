import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

const api = {
  scan: {
    start: (taskId: string, url: string) => ipcRenderer.invoke('scan:start', taskId, url),
    stop: (taskId: string) => ipcRenderer.invoke('scan:stop', taskId),
    pause: (taskId: string) => ipcRenderer.invoke('scan:pause', taskId),
    resume: (taskId: string) => ipcRenderer.invoke('scan:resume', taskId)
  },
  download: {
    start: (taskId: string, files: unknown[], destPath: string) =>
      ipcRenderer.invoke('download:start', taskId, files, destPath),
    pause: (taskId: string) => ipcRenderer.invoke('download:pause', taskId),
    resume: (taskId: string) => ipcRenderer.invoke('download:resume', taskId),
    cancel: (taskId: string, fileId: string) =>
      ipcRenderer.invoke('download:cancel', taskId, fileId),
    cancelAll: (taskId: string) => ipcRenderer.invoke('download:cancelAll', taskId),
    retry: (taskId: string, fileId: string) =>
      ipcRenderer.invoke('download:retry', taskId, fileId),
    setWorkers: (count: number) => ipcRenderer.invoke('download:setWorkers', count)
  },
  task: {
    create: (url: string) => ipcRenderer.invoke('task:create', url),
    remove: (taskId: string) => ipcRenderer.invoke('task:remove', taskId)
  },
  settings: {
    get: () => ipcRenderer.invoke('settings:get'),
    set: (data: unknown) => ipcRenderer.invoke('settings:set', data)
  },
  dialog: {
    selectFolder: () => ipcRenderer.invoke('dialog:selectFolder')
  },
  preview: {
    fetch: (url: string) => ipcRenderer.invoke('preview:fetch', url),
    fetchText: (url: string) => ipcRenderer.invoke('preview:fetchText', url)
  },
  on: (channel: string, callback: (...args: unknown[]) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, ...args: unknown[]): void =>
      callback(...args)
    ipcRenderer.on(channel, listener)
    return (): void => {
      ipcRenderer.removeListener(channel, listener)
    }
  }
}

// Use `contextBridge` APIs to expose Electron APIs to
// renderer only if context isolation is enabled, otherwise
// just add to the DOM global.
if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('api', api)
  } catch (error) {
    console.error(error)
  }
} else {
  // @ts-ignore (define in d.ts)
  window.electron = electronAPI
  // @ts-ignore (define in d.ts)
  window.api = api
}
