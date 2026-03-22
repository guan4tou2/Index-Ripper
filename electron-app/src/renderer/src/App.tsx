import { useEffect, useState } from 'react'
import { Toaster } from 'sonner'
import { TaskTabs } from './components/TaskTabs'
import { Toolbar } from './components/Toolbar'
import { ProgressSection } from './components/ProgressSection'
import { SplitPanel } from './components/SplitPanel'
import { SearchBar } from './components/SearchBar'
import { TypeFilters } from './components/TypeFilters'
import { FileTree } from './components/FileTree'
import { StatusBar } from './components/StatusBar'
import { DownloadsList } from './components/DownloadsList'
import { LogsPanel } from './components/LogsPanel'
import { PreviewPanel } from './components/PreviewPanel'
import { useIpcListeners } from './hooks/useIpcListeners'
import { useTaskStore } from './stores/task-store'

function FilePanel(): JSX.Element {
  return (
    <div className="flex flex-col h-full">
      <SearchBar />
      <TypeFilters />
      <FileTree />
      <StatusBar />
    </div>
  )
}

type RightTab = 'preview' | 'downloads' | 'logs'

function RightPanel(): JSX.Element {
  const [tab, setTab] = useState<RightTab>('preview')
  const previewNodeId = useTaskStore((s) => s.previewNodeId)

  // Auto-switch to preview tab when a file is double-clicked
  useEffect(() => {
    if (previewNodeId) setTab('preview')
  }, [previewNodeId])

  const tabs: { id: RightTab; label: string }[] = [
    { id: 'preview', label: 'Preview' },
    { id: 'downloads', label: 'Downloads' },
    { id: 'logs', label: 'Logs' },
  ]

  return (
    <div className="flex flex-col h-full">
      <div className="flex border-b border-slate-800 bg-slate-900 shrink-0">
        {tabs.map((t) => (
          <button
            key={t.id}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.id
                ? 'text-slate-100 border-b-2 border-blue-500'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-hidden">
        {tab === 'preview' && <PreviewPanel />}
        {tab === 'downloads' && <DownloadsList />}
        {tab === 'logs' && <LogsPanel />}
      </div>
    </div>
  )
}

export default function App(): JSX.Element {
  useIpcListeners()

  return (
    <div className="h-screen bg-slate-950 text-slate-100 flex flex-col overflow-hidden">
      <Toaster
        position="bottom-right"
        theme="dark"
        toastOptions={{
          style: {
            background: '#1e293b',
            border: '1px solid #334155',
            color: '#e2e8f0'
          }
        }}
      />
      <TaskTabs />
      <Toolbar />
      <ProgressSection />
      <SplitPanel
        left={<FilePanel />}
        right={<RightPanel />}
      />
    </div>
  )
}
