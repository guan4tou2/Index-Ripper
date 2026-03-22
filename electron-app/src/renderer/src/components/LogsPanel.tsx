import { useEffect, useRef, useState } from 'react'

export interface LogMessage {
  id: string
  timestamp: Date
  text: string
}

export function LogsPanel(): JSX.Element {
  const [messages, setMessages] = useState<LogMessage[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Expose append function via window for Task 10 IPC integration
  useEffect(() => {
    const handler = (event: CustomEvent<{ text: string }>): void => {
      const msg: LogMessage = {
        id: `${Date.now()}-${Math.random()}`,
        timestamp: new Date(),
        text: event.detail.text
      }
      setMessages((prev) => [...prev, msg])
    }

    window.addEventListener('log-message' as never, handler as EventListener)
    return () => {
      window.removeEventListener('log-message' as never, handler as EventListener)
    }
  }, [])

  if (messages.length === 0) {
    return (
      <div className="flex h-full items-center justify-center bg-slate-950 text-slate-500 text-sm font-mono">
        Waiting for activity...
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto bg-slate-950 p-3">
      <div className="space-y-0.5">
        {messages.map((msg) => (
          <div key={msg.id} className="flex gap-2 text-slate-400 font-mono text-sm leading-5">
            <span className="text-slate-600 shrink-0">
              {msg.timestamp.toLocaleTimeString('en-US', { hour12: false })}
            </span>
            <span className="break-all">{msg.text}</span>
          </div>
        ))}
      </div>
      <div ref={bottomRef} />
    </div>
  )
}
