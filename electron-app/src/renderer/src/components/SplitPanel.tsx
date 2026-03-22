import { useCallback, useRef, useState } from 'react'

interface SplitPanelProps {
  left: React.ReactNode
  right: React.ReactNode
  defaultLeftPercent?: number
  minLeftPercent?: number
  maxLeftPercent?: number
}

export function SplitPanel({
  left,
  right,
  defaultLeftPercent = 65,
  minLeftPercent = 20,
  maxLeftPercent = 80
}: SplitPanelProps): JSX.Element {
  const [leftPercent, setLeftPercent] = useState(defaultLeftPercent)
  const containerRef = useRef<HTMLDivElement>(null)
  const isDragging = useRef(false)

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      isDragging.current = true

      const onMouseMove = (moveEvent: MouseEvent): void => {
        if (!isDragging.current || !containerRef.current) return
        const rect = containerRef.current.getBoundingClientRect()
        const x = moveEvent.clientX - rect.left
        const percent = Math.min(
          maxLeftPercent,
          Math.max(minLeftPercent, (x / rect.width) * 100)
        )
        setLeftPercent(percent)
      }

      const onMouseUp = (): void => {
        isDragging.current = false
        document.removeEventListener('mousemove', onMouseMove)
        document.removeEventListener('mouseup', onMouseUp)
        document.body.style.cursor = ''
        document.body.style.userSelect = ''
      }

      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'
      document.addEventListener('mousemove', onMouseMove)
      document.addEventListener('mouseup', onMouseUp)
    },
    [minLeftPercent, maxLeftPercent]
  )

  return (
    <div ref={containerRef} className="flex flex-1 overflow-hidden">
      {/* Left panel */}
      <div
        className="overflow-auto"
        style={{ width: `${leftPercent}%` }}
      >
        {left}
      </div>

      {/* Divider */}
      <div
        className="w-1 cursor-col-resize bg-slate-800 hover:bg-blue-500 active:bg-blue-500 transition-colors shrink-0"
        onMouseDown={handleMouseDown}
      />

      {/* Right panel */}
      <div
        className="flex-1 overflow-auto"
      >
        {right}
      </div>
    </div>
  )
}
