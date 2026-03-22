import { useTaskStore } from '@/stores/task-store'
import { Plus, X } from 'lucide-react'

function hostnameFromUrl(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url || 'New Tab'
  }
}

export function TaskTabs(): JSX.Element {
  const tasks = useTaskStore((s) => s.tasks)
  const activeTaskId = useTaskStore((s) => s.activeTaskId)
  const createTask = useTaskStore((s) => s.createTask)
  const removeTask = useTaskStore((s) => s.removeTask)
  const setActiveTask = useTaskStore((s) => s.setActiveTask)

  const taskList = Object.values(tasks)

  const handleAdd = async (): Promise<void> => {
    const task = (await window.api.task.create('')) as { id: string; url: string }
    createTask(task.id, task.url)
  }

  const handleRemove = (taskId: string): void => {
    removeTask(taskId)
    window.api.task.remove(taskId)
  }

  return (
    <div className="flex items-center bg-slate-900 border-b border-slate-800 overflow-x-auto">
      {taskList.map((task) => {
        const isActive = task.id === activeTaskId
        return (
          <div
            key={task.id}
            className={`group relative flex items-center gap-1.5 px-3 py-2 text-sm cursor-pointer border-b-2 transition-colors min-w-0 shrink-0 ${
              isActive
                ? 'border-blue-500 bg-slate-800 text-slate-100'
                : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
            onClick={() => setActiveTask(task.id)}
          >
            <span className="truncate max-w-[140px]">
              {hostnameFromUrl(task.url) || 'New Tab'}
            </span>
            <button
              className="ml-1 p-0.5 rounded hover:bg-slate-700 text-slate-500 hover:text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity"
              onClick={(e) => {
                e.stopPropagation()
                handleRemove(task.id)
              }}
              title="Close tab"
            >
              <X className="size-3" />
            </button>
          </div>
        )
      })}
      <button
        className="flex items-center justify-center p-2 text-slate-500 hover:text-slate-300 hover:bg-slate-800/50 transition-colors"
        onClick={handleAdd}
        title="New tab"
      >
        <Plus className="size-4" />
      </button>
    </div>
  )
}
