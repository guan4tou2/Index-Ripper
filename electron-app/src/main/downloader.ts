import * as http from 'http'
import * as https from 'https'
import { createWriteStream, mkdirSync, unlinkSync, existsSync } from 'fs'
import { dirname } from 'path'
import { EventEmitter } from 'events'
import type { DownloadItem } from '../shared/types'

type PQueueType = import('p-queue').default

interface DownloadCallbacks {
  onProgress?: (fileId: string, percent: number, speed: number) => void
  onStatus?: (fileId: string, status: DownloadItem['status']) => void
  onLog?: (message: string) => void
  onFinished?: (completed: number, total: number) => void
}

interface DownloadFile {
  id: string
  url: string
  destPath: string
  fileName: string
}

const MAX_CONCURRENCY = 10
const MIN_CONCURRENCY = 1
const MAX_ATTEMPTS = 3
const BASE_BACKOFF_MS = 1000
const PROGRESS_INTERVAL_MS = 500

export class Downloader extends EventEmitter {
  private queue: PQueueType | null = null
  private queueReady: Promise<void>
  private concurrency: number
  private controllers = new Map<string, AbortController>()
  private _paused = false
  private _resumeResolvers: Array<() => void> = []

  constructor(concurrency = 5) {
    super()
    this.concurrency = Math.min(MAX_CONCURRENCY, Math.max(MIN_CONCURRENCY, concurrency))
    this.queueReady = this._initQueue()
  }

  private async _initQueue(): Promise<void> {
    const { default: PQueue } = await import('p-queue')
    this.queue = new PQueue({ concurrency: this.concurrency })
  }

  private async getQueue(): Promise<PQueueType> {
    await this.queueReady
    return this.queue!
  }

  async setConcurrency(n: number): Promise<void> {
    this.concurrency = Math.min(MAX_CONCURRENCY, Math.max(MIN_CONCURRENCY, n))
    const q = await this.getQueue()
    q.concurrency = this.concurrency
  }

  pause(): void {
    if (this._paused) return
    this._paused = true
    this.getQueue().then((q) => q.pause()).catch(() => {})
  }

  resume(): void {
    if (!this._paused) return
    this._paused = false
    for (const resolve of this._resumeResolvers) resolve()
    this._resumeResolvers = []
    this.getQueue().then((q) => q.start()).catch(() => {})
  }

  private waitIfPaused(): Promise<void> {
    if (!this._paused) return Promise.resolve()
    return new Promise<void>((resolve) => {
      this._resumeResolvers.push(resolve)
    })
  }

  cancelFile(fileId: string): void {
    const ctrl = this.controllers.get(fileId)
    if (ctrl) {
      ctrl.abort()
      this.controllers.delete(fileId)
    }
  }

  async cancelAll(): Promise<void> {
    const q = await this.getQueue()
    q.clear()
    for (const ctrl of this.controllers.values()) {
      ctrl.abort()
    }
    this.controllers.clear()
  }

  async downloadFiles(files: DownloadFile[], callbacks: DownloadCallbacks): Promise<void> {
    const q = await this.getQueue()
    let completed = 0
    const total = files.length

    const tasks = files.map((file) =>
      q.add(async () => {
        await this.waitIfPaused()
        await this.downloadOne(file, callbacks, 1)
        completed++
      })
    )

    await Promise.allSettled(tasks)
    callbacks.onFinished?.(completed, total)
  }

  async downloadOne(file: DownloadFile, callbacks: DownloadCallbacks, attempt: number): Promise<void> {
    const { id, url, destPath, fileName } = file

    callbacks.onStatus?.(id, 'downloading')
    callbacks.onLog?.(`[${fileName}] Starting download (attempt ${attempt}/${MAX_ATTEMPTS})`)

    mkdirSync(dirname(destPath), { recursive: true })

    const controller = new AbortController()
    this.controllers.set(id, controller)

    return new Promise<void>((resolve, reject) => {
      const isHttps = url.startsWith('https')
      const client = isHttps ? https : http

      const req = client.get(url, { signal: controller.signal }, (res) => {
        const statusCode = res.statusCode ?? 0

        // Follow redirects
        if (statusCode >= 300 && statusCode < 400 && res.headers.location) {
          res.resume()
          this.controllers.delete(id)
          const redirectedFile = { ...file, url: new URL(res.headers.location, url).href }
          this.downloadOne(redirectedFile, callbacks, attempt).then(resolve).catch(reject)
          return
        }

        // Retry on 5xx
        if (statusCode >= 500) {
          res.resume()
          this.controllers.delete(id)
          if (attempt < MAX_ATTEMPTS) {
            const backoff = BASE_BACKOFF_MS * Math.pow(2, attempt - 1)
            callbacks.onLog?.(`[${fileName}] Server error ${statusCode}, retrying in ${backoff}ms`)
            setTimeout(() => {
              this.downloadOne(file, callbacks, attempt + 1).then(resolve).catch(reject)
            }, backoff)
          } else {
            callbacks.onStatus?.(id, 'failed')
            callbacks.onLog?.(`[${fileName}] Failed after ${MAX_ATTEMPTS} attempts (HTTP ${statusCode})`)
            reject(new Error(`HTTP ${statusCode}`))
          }
          return
        }

        if (statusCode < 200 || statusCode >= 300) {
          res.resume()
          this.controllers.delete(id)
          callbacks.onStatus?.(id, 'failed')
          callbacks.onLog?.(`[${fileName}] HTTP error ${statusCode}`)
          reject(new Error(`HTTP ${statusCode}`))
          return
        }

        const totalSize = parseInt(res.headers['content-length'] ?? '0', 10) || 0
        const writeStream = createWriteStream(destPath)
        let bytesDownloaded = 0
        let lastProgressTime = Date.now()
        let lastProgressBytes = 0

        const progressTimer = setInterval(() => {
          const now = Date.now()
          const elapsed = (now - lastProgressTime) / 1000
          const speed = elapsed > 0 ? (bytesDownloaded - lastProgressBytes) / elapsed : 0
          lastProgressTime = now
          lastProgressBytes = bytesDownloaded
          const percent = totalSize > 0 ? Math.min(100, (bytesDownloaded / totalSize) * 100) : 0
          callbacks.onProgress?.(id, percent, speed)
        }, PROGRESS_INTERVAL_MS)

        const cleanup = (deleteFile: boolean): void => {
          clearInterval(progressTimer)
          writeStream.destroy()
          this.controllers.delete(id)
          if (deleteFile && existsSync(destPath)) {
            try { unlinkSync(destPath) } catch { /* ignore */ }
          }
        }

        res.on('data', (chunk: Buffer) => {
          bytesDownloaded += chunk.length
          writeStream.write(chunk)
        })

        res.on('end', () => {
          cleanup(false)
          callbacks.onProgress?.(id, 100, 0)
          callbacks.onStatus?.(id, 'completed')
          callbacks.onLog?.(`[${fileName}] Complete (${bytesDownloaded} bytes)`)
          resolve()
        })

        res.on('error', (err) => {
          cleanup(true)
          callbacks.onStatus?.(id, 'failed')
          callbacks.onLog?.(`[${fileName}] Error: ${err.message}`)
          reject(err)
        })

        writeStream.on('error', (err) => {
          cleanup(true)
          callbacks.onStatus?.(id, 'failed')
          callbacks.onLog?.(`[${fileName}] Write error: ${err.message}`)
          reject(err)
        })
      })

      req.on('error', (err) => {
        if (controller.signal.aborted) {
          callbacks.onStatus?.(id, 'cancelled')
          callbacks.onLog?.(`[${fileName}] Cancelled`)
          resolve()
          return
        }
        this.controllers.delete(id)
        if (attempt < MAX_ATTEMPTS) {
          const backoff = BASE_BACKOFF_MS * Math.pow(2, attempt - 1)
          callbacks.onLog?.(`[${fileName}] Network error, retrying in ${backoff}ms: ${err.message}`)
          setTimeout(() => {
            this.downloadOne(file, callbacks, attempt + 1).then(resolve).catch(reject)
          }, backoff)
        } else {
          callbacks.onStatus?.(id, 'failed')
          callbacks.onLog?.(`[${fileName}] Failed: ${err.message}`)
          reject(err)
        }
      })
    })
  }
}
