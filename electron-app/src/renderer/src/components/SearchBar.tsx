import { useState, useRef, useEffect, useCallback } from 'react'
import { Search, X } from 'lucide-react'
import { useFileTree } from '@/hooks/useFileTree'

export function SearchBar(): JSX.Element {
  const [query, setQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const { searchFilter } = useFileTree()

  const handleChange = useCallback(
    (value: string) => {
      setQuery(value)
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        searchFilter(value)
      }, 300)
    },
    [searchFilter]
  )

  const handleClear = useCallback(() => {
    setQuery('')
    if (debounceRef.current) clearTimeout(debounceRef.current)
    searchFilter('')
    inputRef.current?.focus()
  }, [searchFilter])

  // Ctrl/Cmd+F focuses the search input
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent): void => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'f') {
        e.preventDefault()
        inputRef.current?.focus()
        inputRef.current?.select()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  return (
    <div className="flex items-center gap-2 px-3 py-2 border-b border-slate-800 bg-slate-900/50">
      <Search className="size-4 text-slate-500 shrink-0" />
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => handleChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') handleClear()
        }}
        placeholder="Search files..."
        className="flex-1 min-w-0 bg-transparent text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none"
      />
      {query && (
        <button
          onClick={handleClear}
          className="flex items-center justify-center size-5 rounded-full bg-slate-700 hover:bg-slate-600 text-slate-400 hover:text-slate-200 shrink-0 transition-colors"
          title="Clear search (Esc)"
        >
          <X className="size-3" />
        </button>
      )}
    </div>
  )
}
