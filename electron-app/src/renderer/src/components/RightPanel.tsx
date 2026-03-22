import { useState } from 'react'
import { DownloadsList } from './DownloadsList'
import { LogsPanel } from './LogsPanel'

type ActiveTab = 'downloads' | 'logs'

export function RightPanel(): JSX.Element {
  const [activeTab, setActiveTab] = useState<ActiveTab>('downloads')

  return (
    <div className="flex flex-col h-full">
      <div className="flex border-b border-slate-800 px-2 shrink-0">
        <button
          onClick={() => setActiveTab('downloads')}
          className={`px-4 py-2 text-sm ${
            activeTab === 'downloads'
              ? 'text-slate-100 border-b-2 border-blue-500'
              : 'text-slate-500 hover:text-slate-300'
          } transition-colors`}
        >
          Downloads
        </button>
        <button
          onClick={() => setActiveTab('logs')}
          className={`px-4 py-2 text-sm ${
            activeTab === 'logs'
              ? 'text-slate-100 border-b-2 border-blue-500'
              : 'text-slate-500 hover:text-slate-300'
          } transition-colors`}
        >
          Logs
        </button>
      </div>
      <div className="flex-1 overflow-hidden">
        {activeTab === 'downloads' ? <DownloadsList /> : <LogsPanel />}
      </div>
    </div>
  )
}
