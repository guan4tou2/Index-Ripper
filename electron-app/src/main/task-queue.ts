import { randomUUID } from 'crypto'
import type { Task } from '../shared/types'
import { Scanner } from './scanner'
import { Downloader } from './downloader'
import { defaultDownloadFolder } from './utils'

export class TaskQueue {
  tasks = new Map<string, { task: Task; scanner: Scanner; downloader: Downloader }>()

  createTask(url: string): Task {
    const id = randomUUID()
    const task: Task = {
      id,
      url,
      status: 'idle',
      nodes: {},
      roots: [],
      checkedFiles: [],
      downloads: {},
      scanProgress: { scanned: 0, total: 0 },
      downloadPath: defaultDownloadFolder(url)
    }
    this.tasks.set(id, { task, scanner: new Scanner(), downloader: new Downloader() })
    return task
  }

  getTask(taskId: string) {
    return this.tasks.get(taskId)
  }

  removeTask(taskId: string): void {
    const entry = this.tasks.get(taskId)
    if (entry) {
      entry.scanner.abort()
      entry.downloader.cancelAll()
      this.tasks.delete(taskId)
    }
  }

  allTasks(): Task[] {
    return [...this.tasks.values()].map((e) => e.task)
  }
}
