import { useEffect } from 'react'

export interface Api {
  scan: {
    start: (taskId: string, url: string) => Promise<unknown>
    stop: (taskId: string) => Promise<unknown>
    pause: (taskId: string) => Promise<unknown>
    resume: (taskId: string) => Promise<unknown>
  }
  download: {
    start: (taskId: string, files: unknown[], destPath: string) => Promise<unknown>
    pause: (taskId: string) => Promise<unknown>
    resume: (taskId: string) => Promise<unknown>
    cancel: (taskId: string, fileId: string) => Promise<unknown>
    cancelAll: (taskId: string) => Promise<unknown>
    retry: (taskId: string, fileId: string) => Promise<unknown>
    setWorkers: (count: number) => Promise<unknown>
  }
  task: {
    create: (url: string) => Promise<unknown>
    remove: (taskId: string) => Promise<unknown>
  }
  settings: {
    get: () => Promise<unknown>
    set: (data: unknown) => Promise<unknown>
  }
  dialog: {
    selectFolder: () => Promise<string | null>
  }
  preview: {
    fetch: (url: string) => Promise<{ dataUrl: string; contentType: string }>
    fetchText: (url: string) => Promise<string>
  }
  on: (channel: string, callback: (...args: unknown[]) => void) => () => void
}

declare global {
  interface Window {
    api: Api
  }
}

export function useIpcEvent(channel: string, callback: (...args: unknown[]) => void): void {
  useEffect(() => {
    const unsubscribe = window.api.on(channel, callback)
    return unsubscribe
  }, [channel, callback])
}
