import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/router'
import { Search, FileText, MessageSquare, Compass, X, ArrowRight, Upload, Sparkles, Command } from 'lucide-react'
import { DocumentResponse } from '@/lib/api'

interface CommandPaletteProps {
  isOpen: boolean
  onClose: () => void
  documents: DocumentResponse[]
  onOpenUpload: () => void
}

export default function CommandPalette({ isOpen, onClose, documents, onOpenUpload }: CommandPaletteProps) {
  const router = useRouter()
  const [query, setQuery] = useState('')

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        if (isOpen) onClose()
        else setQuery('')
      }
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const filteredDocs = documents.filter(doc =>
    doc.filename.toLowerCase().includes(query.toLowerCase())
  )

  const quickActions = [
    {
      id: 'upload',
      title: 'Upload Research Paper',
      desc: 'Process PDF with vector embeddings',
      icon: Upload,
      color: 'text-blue-500 bg-blue-50 dark:bg-blue-900/30',
      action: () => {
        onClose()
        onOpenUpload()
      }
    },
    {
      id: 'chat',
      title: 'Start New AI Chat',
      desc: 'Ask questions & extract insights',
      icon: MessageSquare,
      color: 'text-emerald-500 bg-emerald-50 dark:bg-emerald-900/30',
      action: () => {
        onClose()
        router.push('/chat')
      }
    },
    {
      id: 'search',
      title: 'Academic Search Engine',
      desc: 'Hybrid BM25 + vector document search',
      icon: Compass,
      color: 'text-purple-500 bg-purple-50 dark:bg-purple-900/30',
      action: () => {
        onClose()
        router.push('/search')
      }
    }
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-slate-900/60 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200/80 dark:border-slate-800 w-full max-w-2xl overflow-hidden transform transition-all">
        {/* Input Bar */}
        <div className="flex items-center px-6 py-4 border-b border-slate-100 dark:border-slate-800 gap-3">
          <Search className="w-5 h-5 text-slate-400" />
          <input
            type="text"
            placeholder="Search documents, commands, or ask AI..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
            className="flex-1 text-slate-800 dark:text-slate-100 placeholder-slate-400 bg-transparent border-none outline-none focus:ring-0 text-base font-medium"
          />
          <div className="flex items-center gap-1.5 px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded-lg text-xs font-semibold text-slate-500">
            <Command className="w-3 h-3" /> K
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="max-h-96 overflow-y-auto p-4 space-y-6">
          {/* Quick Actions */}
          {!query && (
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider px-3 mb-2">
                Quick Actions
              </p>
              <div className="space-y-1">
                {quickActions.map((act) => {
                  const Icon = act.icon
                  return (
                    <button
                      key={act.id}
                      onClick={act.action}
                      className="w-full flex items-center justify-between p-3 rounded-2xl hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors group text-left"
                    >
                      <div className="flex items-center gap-3">
                        <div className={`p-2.5 rounded-xl ${act.color}`}>
                          <Icon className="w-5 h-5" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                            {act.title}
                          </p>
                          <p className="text-xs text-slate-500 dark:text-slate-400">
                            {act.desc}
                          </p>
                        </div>
                      </div>
                      <ArrowRight className="w-4 h-4 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Document Results */}
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider px-3 mb-2">
              {query ? `Search Results (${filteredDocs.length})` : 'Recent Research Documents'}
            </p>
            {filteredDocs.length === 0 ? (
              <div className="p-6 text-center text-slate-500 dark:text-slate-400 text-sm">
                No documents found matching "{query}"
              </div>
            ) : (
              <div className="space-y-1">
                {filteredDocs.slice(0, 5).map((doc) => (
                  <button
                    key={doc.id}
                    onClick={() => {
                      onClose()
                      router.push(`/chat?document_id=${doc.id}`)
                    }}
                    className="w-full flex items-center justify-between p-3 rounded-2xl hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors group text-left"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="p-2.5 rounded-xl bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 flex-shrink-0">
                        <FileText className="w-5 h-5" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 truncate group-hover:text-blue-600 dark:group-hover:text-blue-400">
                          {doc.filename}
                        </p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          {doc.page_count ? `${doc.page_count} pages` : 'PDF Document'} • Status: {doc.processing_status}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="text-xs px-2.5 py-1 rounded-full bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400 font-medium flex items-center gap-1">
                        <Sparkles className="w-3 h-3" /> Chat
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="px-6 py-3 bg-slate-50 dark:bg-slate-900/80 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
          <span>Navigate with arrows</span>
          <span>Press <kbd className="px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">ESC</kbd> to exit</span>
        </div>
      </div>
    </div>
  )
}
