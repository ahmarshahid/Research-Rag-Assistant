import React, { useState, useEffect } from 'react'
import { Activity, Bookmark, StickyNote, Target, ChevronRight, CheckCircle2, Star, Plus, Trash2 } from 'lucide-react'
import { DocumentResponse } from '@/lib/api'

interface SidebarRightProps {
  documents: DocumentResponse[]
}

export default function SidebarRight({ documents }: SidebarRightProps) {
  const [activeTab, setActiveTab] = useState<'activity' | 'notes' | 'milestones'>('activity')
  const [note, setNote] = useState('')
  const [milestones, setMilestones] = useState([
    { id: 1, title: 'Upload Quantum Computing papers', done: true },
    { id: 2, title: 'Extract RAG citations for thesis', done: false },
    { id: 3, title: 'Compare Transformer benchmarks', done: false },
  ])

  useEffect(() => {
    const saved = localStorage.getItem('research_scratchpad')
    if (saved) setNote(saved)
  }, [])

  const handleNoteChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value
    setNote(val)
    localStorage.setItem('research_scratchpad', val)
  }

  const toggleMilestone = (id: number) => {
    setMilestones(prev => prev.map(m => m.id === id ? { ...m, done: !m.done } : m))
  }

  return (
    <aside className="w-full xl:w-80 space-y-6 flex-shrink-0">
      {/* Widget Tabs Header */}
      <div className="bg-white dark:bg-slate-900 rounded-3xl p-2 shadow-sm border border-slate-200/60 dark:border-slate-800/80 flex items-center justify-between gap-1">
        <button
          onClick={() => setActiveTab('activity')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-2xl text-xs font-bold transition-all ${
            activeTab === 'activity'
              ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'
          }`}
        >
          <Activity className="w-3.5 h-3.5" /> Activity
        </button>
        <button
          onClick={() => setActiveTab('notes')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-2xl text-xs font-bold transition-all ${
            activeTab === 'notes'
              ? 'bg-purple-600 text-white shadow-md shadow-purple-500/20'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'
          }`}
        >
          <StickyNote className="w-3.5 h-3.5" /> Notes
        </button>
        <button
          onClick={() => setActiveTab('milestones')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-2xl text-xs font-bold transition-all ${
            activeTab === 'milestones'
              ? 'bg-emerald-600 text-white shadow-md shadow-emerald-500/20'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'
          }`}
        >
          <Target className="w-3.5 h-3.5" /> Goals
        </button>
      </div>

      {/* Tab Contents */}
      {activeTab === 'activity' && (
        <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 shadow-sm border border-slate-200/60 dark:border-slate-800/80 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <Activity className="w-4 h-4 text-blue-600" /> Recent Activity
            </h3>
            <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950 text-blue-600">Live Feed</span>
          </div>

          <div className="space-y-3 relative before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-100 dark:before:bg-slate-800">
            {documents.length > 0 ? (
              documents.slice(0, 4).map((doc, idx) => (
                <div key={doc.id} className="relative pl-6 text-xs">
                  <div className="absolute left-0 top-1 w-4 h-4 rounded-full bg-blue-500 ring-4 ring-white dark:ring-slate-900 flex items-center justify-center text-[8px] text-white font-bold">
                    ✓
                  </div>
                  <p className="font-semibold text-slate-800 dark:text-slate-200 truncate">
                    Uploaded {doc.filename}
                  </p>
                  <p className="text-slate-400 text-[11px] mt-0.5">
                    {new Date(doc.upload_timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} • Vectorized
                  </p>
                </div>
              ))
            ) : (
              <p className="pl-6 text-xs text-slate-400 italic">No recent activity logged yet.</p>
            )}
          </div>
        </div>
      )}

      {activeTab === 'notes' && (
        <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 shadow-sm border border-slate-200/60 dark:border-slate-800/80 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <StickyNote className="w-4 h-4 text-purple-600" /> Research Scratchpad
            </h3>
            <span className="text-[10px] text-slate-400">Auto-saved</span>
          </div>
          <textarea
            value={note}
            onChange={handleNoteChange}
            placeholder="Jot down quick ideas, citations, or paper summaries here..."
            rows={6}
            className="w-full p-3 text-xs rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 text-slate-800 dark:text-slate-200 placeholder-slate-400 focus:ring-2 focus:ring-purple-500 outline-none resize-none"
          />
        </div>
      )}

      {activeTab === 'milestones' && (
        <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 shadow-sm border border-slate-200/60 dark:border-slate-800/80 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <Target className="w-4 h-4 text-emerald-600" /> Research Milestones
            </h3>
          </div>
          <div className="space-y-2">
            {milestones.map((m) => (
              <button
                key={m.id}
                onClick={() => toggleMilestone(m.id)}
                className={`w-full flex items-center gap-3 p-3 rounded-2xl text-left text-xs font-medium transition-all ${
                  m.done
                    ? 'bg-emerald-50/60 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-400 line-through'
                    : 'bg-slate-50 dark:bg-slate-800/50 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                <CheckCircle2 className={`w-4 h-4 flex-shrink-0 ${m.done ? 'text-emerald-500' : 'text-slate-300 dark:text-slate-600'}`} />
                <span className="flex-1">{m.title}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Bookmarks / Favorites Quick Widget */}
      <div className="bg-gradient-to-br from-slate-900 to-slate-800 dark:from-slate-900 dark:to-slate-950 rounded-3xl p-6 text-white shadow-xl space-y-4 relative overflow-hidden">
        <div className="absolute -right-6 -bottom-6 w-32 h-32 bg-blue-500/10 rounded-full blur-2xl"></div>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold flex items-center gap-2 text-white">
            <Star className="w-4 h-4 text-amber-400 fill-amber-400" /> Starred Favorites
          </h3>
          <span className="text-xs px-2 py-0.5 rounded-full bg-white/10 text-white/80 font-mono">
            {documents.length}
          </span>
        </div>
        <p className="text-xs text-slate-300 leading-relaxed">
          Quickly access pinned research papers and vector embeddings for instant chat sessions.
        </p>
        <div className="pt-2">
          <div className="text-xs font-semibold text-blue-400 flex items-center gap-1 cursor-pointer hover:underline">
            Manage bookmarks <ChevronRight className="w-3.5 h-3.5" />
          </div>
        </div>
      </div>
    </aside>
  )
}
