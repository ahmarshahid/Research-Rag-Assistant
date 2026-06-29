import { useEffect, useState } from 'react'
import { useRouter } from 'next/router'
import Link from 'next/link'
import { useAuthStore } from '@/lib/auth-store'
import { apiClient, DocumentResponse, ChatSessionResponse } from '@/lib/api'
import toast from 'react-hot-toast'
import { motion, AnimatePresence } from 'framer-motion'
import {
  UploadCloud,
  MessageSquare,
  Search,
  LogOut,
  FileText,
  Sparkles,
  Layers,
  HardDrive,
  Clock,
  CheckCircle2,
  AlertCircle,
  Plus,
  Eye,
  Download,
  Edit3,
  Trash2,
  Bell,
  Sun,
  Moon,
  Command,
  ChevronRight,
  Filter,
  Grid,
  List,
  Compass,
  ArrowUpRight,
  User as UserIcon
} from 'lucide-react'

import CommandPalette from '@/components/CommandPalette'
import UploadModal from '@/components/UploadModal'
import DocumentViewModal from '@/components/DocumentViewModal'
import RenameModal from '@/components/RenameModal'
import SidebarRight from '@/components/SidebarRight'

export default function DashboardPage() {
  const router = useRouter()
  const { user, logout, checkAuth } = useAuthStore()

  // State
  const [documents, setDocuments] = useState<DocumentResponse[]>([])
  const [conversations, setConversations] = useState<ChatSessionResponse[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchFilter, setSearchFilter] = useState('')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [darkMode, setDarkMode] = useState(false)

  // Modals state
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false)
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false)
  const [selectedDocForView, setSelectedDocForView] = useState<DocumentResponse | null>(null)
  const [selectedDocForRename, setSelectedDocForRename] = useState<DocumentResponse | null>(null)
  const [showNotifications, setShowNotifications] = useState(false)
  const [showUserDropdown, setShowUserDropdown] = useState(false)

  // Dark mode handler
  useEffect(() => {
    if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      setDarkMode(true)
      document.documentElement.classList.add('dark')
    } else {
      setDarkMode(false)
      document.documentElement.classList.remove('dark')
    }
  }, [])

  const toggleDarkMode = () => {
    if (darkMode) {
      document.documentElement.classList.remove('dark')
      localStorage.theme = 'light'
      setDarkMode(false)
    } else {
      document.documentElement.classList.add('dark')
      localStorage.theme = 'dark'
      setDarkMode(true)
    }
  }

  // Auth & Initial load
  useEffect(() => {
    const init = async () => {
      await checkAuth()
      if (!user) {
        router.push('/auth/login')
        return
      }
      fetchDashboardData()
    }
    init()
  }, [])

  const fetchDashboardData = async () => {
    setIsLoading(true)
    try {
      const [docsData, chatsData] = await Promise.all([
        apiClient.listDocuments().catch(() => []),
        apiClient.listChatSessions().catch(() => [])
      ])
      setDocuments(docsData)
      setConversations(chatsData)
    } catch {
      toast.error('Failed to update dashboard data')
    } finally {
      setIsLoading(false)
    }
  }

  const handleDeleteDocument = async (id: string, filename: string) => {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) return
    try {
      await apiClient.deleteDocument(id)
      toast.success('Document deleted successfully')
      setDocuments((prev) => prev.filter((d) => d.id !== id))
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to delete document')
    }
  }

  const handleRenameSuccess = (id: string, newName: string) => {
    setDocuments((prev) =>
      prev.map((d) => (d.id === id ? { ...d, filename: newName } : d))
    )
  }

  const handleLogout = async () => {
    await logout()
    router.push('/auth/login')
  }

  // Greeting logic
  const getGreeting = () => {
    const hour = new Date().getHours()
    if (hour < 12) return 'Good morning'
    if (hour < 18) return 'Good afternoon'
    return 'Good evening'
  }

  if (!user) return null

  // Stats calculation
  const totalStorageMB = (
    documents.reduce((acc, d) => acc + (d.file_size || 0), 0) / (1024 * 1024)
  ).toFixed(1)

  const filteredDocs = documents.filter((d) =>
    d.filename.toLowerCase().includes(searchFilter.toLowerCase())
  )

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-sans transition-colors duration-300">
      {/* ── STICKY TOP NAVIGATION BAR ────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 w-full bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200/80 dark:border-slate-800/80 transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          {/* Brand Logo */}
          <Link href="/dashboard" className="flex items-center gap-3 group">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-blue-600 via-purple-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20 group-hover:scale-105 transition-transform">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <span className="font-heading font-extrabold text-lg bg-gradient-to-r from-blue-600 via-purple-600 to-indigo-600 bg-clip-text text-transparent">
                Research Studio
              </span>
              <span className="hidden sm:inline-block ml-2 text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800">
                AI SaaS
              </span>
            </div>
          </Link>

          {/* Global Search Trigger Bar */}
          <div className="flex-1 max-w-md mx-4 hidden md:block">
            <button
              onClick={() => setIsCommandPaletteOpen(true)}
              className="w-full flex items-center justify-between px-4 py-2 rounded-2xl bg-slate-100/80 dark:bg-slate-800/60 border border-slate-200/60 dark:border-slate-700/60 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:border-blue-400 transition-all text-sm group"
            >
              <div className="flex items-center gap-2.5">
                <Search className="w-4 h-4 text-slate-400 group-hover:text-blue-500 transition-colors" />
                <span>Search documents, vectors, or commands...</span>
              </div>
              <div className="flex items-center gap-1 px-2 py-0.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-500">
                <Command className="w-3 h-3" /> K
              </div>
            </button>
          </div>

          {/* User Controls & Actions */}
          <div className="flex items-center gap-3">
            {/* Dark mode toggle */}
            <button
              onClick={toggleDarkMode}
              className="p-2.5 rounded-2xl text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              title="Toggle theme"
            >
              {darkMode ? <Sun className="w-5 h-5 text-amber-400" /> : <Moon className="w-5 h-5 text-slate-600" />}
            </button>

            {/* Notifications Dropdown */}
            <div className="relative">
              <button
                onClick={() => setShowNotifications(!showNotifications)}
                className="p-2.5 rounded-2xl text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors relative"
              >
                <Bell className="w-5 h-5" />
                <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-blue-600 ring-2 ring-white dark:ring-slate-900" />
              </button>

              <AnimatePresence>
                {showNotifications && (
                  <motion.div
                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 10, scale: 0.95 }}
                    className="absolute right-0 mt-2 w-80 rounded-3xl bg-white dark:bg-slate-900 shadow-2xl border border-slate-200 dark:border-slate-800 p-4 z-50"
                  >
                    <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">Notifications</h4>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950 text-blue-600 font-bold">2 New</span>
                    </div>
                    <div className="mt-3 space-y-3">
                      <div className="flex gap-3 text-xs">
                        <div className="p-2 rounded-xl bg-emerald-50 dark:bg-emerald-950 text-emerald-600 flex-shrink-0">
                          <CheckCircle2 className="w-4 h-4" />
                        </div>
                        <div>
                          <p className="font-semibold text-slate-800 dark:text-slate-200">System Ready</p>
                          <p className="text-slate-500 text-[11px]">PostgreSQL & Redis connected successfully.</p>
                        </div>
                      </div>
                      <div className="flex gap-3 text-xs">
                        <div className="p-2 rounded-xl bg-blue-50 dark:bg-blue-950 text-blue-600 flex-shrink-0">
                          <Sparkles className="w-4 h-4" />
                        </div>
                        <div>
                          <p className="font-semibold text-slate-800 dark:text-slate-200">AI Model Loaded</p>
                          <p className="text-slate-500 text-[11px]">BAAI/bge-base-en embeddings pipeline active.</p>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* User Profile Menu */}
            <div className="relative">
              <button
                onClick={() => setShowUserDropdown(!showUserDropdown)}
                className="flex items-center gap-2.5 p-1.5 pl-3 rounded-2xl hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors border border-slate-200/60 dark:border-slate-800"
              >
                <span className="text-xs font-bold text-slate-700 dark:text-slate-200 hidden sm:inline-block">
                  {user.username || user.email.split('@')[0]}
                </span>
                <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-purple-600 flex items-center justify-center text-white font-bold text-xs shadow-sm">
                  {(user.username || user.email)[0].toUpperCase()}
                </div>
              </button>

              <AnimatePresence>
                {showUserDropdown && (
                  <motion.div
                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 10, scale: 0.95 }}
                    className="absolute right-0 mt-2 w-60 rounded-3xl bg-white dark:bg-slate-900 shadow-2xl border border-slate-200 dark:border-slate-800 p-2 z-50"
                  >
                    <div className="p-3 border-b border-slate-100 dark:border-slate-800">
                      <p className="text-xs font-bold text-slate-900 dark:text-slate-100 truncate">{user.username}</p>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">{user.email}</p>
                    </div>
                    <div className="py-1">
                      <button
                        onClick={handleLogout}
                        className="w-full flex items-center gap-2 px-3 py-2 text-xs font-semibold text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 rounded-xl transition-colors"
                      >
                        <LogOut className="w-4 h-4" /> Sign Out
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </header>

      {/* ── MAIN CONTAINER ─────────────────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-10">
        {/* ── HERO SECTION ───────────────────────────────────────────────────── */}
        <section className="relative rounded-3xl p-8 sm:p-10 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white overflow-hidden shadow-2xl border border-slate-800">
          {/* Background decorative elements */}
          <div className="absolute top-0 right-0 w-96 h-96 bg-blue-600/20 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none" />
          <div className="absolute bottom-0 left-1/3 w-80 h-80 bg-purple-600/20 rounded-full blur-3xl -mb-20 pointer-events-none" />

          <div className="relative z-10 max-w-3xl space-y-4">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/10 backdrop-blur-md border border-white/10 text-xs font-semibold text-blue-300">
              <Sparkles className="w-4 h-4 text-amber-400" /> Advanced RAG & Vector Intelligence
            </div>
            <h2 className="font-heading text-3xl sm:text-4xl font-extrabold tracking-tight leading-tight">
              {getGreeting()}, <span className="bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">{user.username || user.email.split('@')[0]}</span>! 👋
            </h2>
            <p className="text-slate-300 text-sm sm:text-base leading-relaxed max-w-2xl">
              Upload your research papers, extract key citations, and interact with an advanced AI copilot backed by PostgreSQL, ChromaDB, and hybrid semantic search.
            </p>
            <div className="pt-2 flex flex-wrap gap-3">
              <button
                onClick={() => setIsUploadModalOpen(true)}
                className="px-6 py-3 rounded-2xl font-semibold text-xs sm:text-sm bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white shadow-lg shadow-blue-500/30 flex items-center gap-2 transition-all hover:scale-105"
              >
                <UploadCloud className="w-4 h-4" /> Upload Research Paper
              </button>
              <button
                onClick={() => setIsCommandPaletteOpen(true)}
                className="px-5 py-3 rounded-2xl font-semibold text-xs sm:text-sm bg-white/10 hover:bg-white/20 backdrop-blur-md text-white border border-white/15 flex items-center gap-2 transition-all"
              >
                <Command className="w-4 h-4" /> Open Palette (Ctrl+K)
              </button>
            </div>
          </div>
        </section>

        {/* ── ANALYTICS METRICS CARDS ────────────────────────────────────────── */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 shadow-sm border border-slate-200/60 dark:border-slate-800/80 hover:shadow-xl transition-all group">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Total Papers</span>
              <div className="p-3 rounded-2xl bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400 group-hover:scale-110 transition-transform">
                <FileText className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline justify-between">
              <span className="text-3xl font-extrabold text-slate-900 dark:text-slate-100 font-heading">{documents.length}</span>
              <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 flex items-center gap-0.5">+100% active</span>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 shadow-sm border border-slate-200/60 dark:border-slate-800/80 hover:shadow-xl transition-all group">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Conversations</span>
              <div className="p-3 rounded-2xl bg-purple-50 dark:bg-purple-950 text-purple-600 dark:text-purple-400 group-hover:scale-110 transition-transform">
                <MessageSquare className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline justify-between">
              <span className="text-3xl font-extrabold text-slate-900 dark:text-slate-100 font-heading">{conversations.length}</span>
              <span className="text-xs font-semibold text-purple-600 dark:text-purple-400">AI Chat Sessions</span>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 shadow-sm border border-slate-200/60 dark:border-slate-800/80 hover:shadow-xl transition-all group">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Vector Queries</span>
              <div className="p-3 rounded-2xl bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 group-hover:scale-110 transition-transform">
                <Compass className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline justify-between">
              <span className="text-3xl font-extrabold text-slate-900 dark:text-slate-100 font-heading">24</span>
              <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400">Hybrid BM25</span>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 shadow-sm border border-slate-200/60 dark:border-slate-800/80 hover:shadow-xl transition-all group">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Storage Used</span>
              <div className="p-3 rounded-2xl bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 group-hover:scale-110 transition-transform">
                <HardDrive className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 space-y-2">
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 font-heading">{totalStorageMB} MB</span>
                <span className="text-xs text-slate-400 font-medium">of 1 GB</span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${Math.min(100, Number(totalStorageMB) * 2)}%` }} />
              </div>
            </div>
          </div>
        </section>

        {/* ── FEATURE CARDS ───────────────────────────────────────────────────── */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1: Upload Research Paper */}
          <div
            onClick={() => setIsUploadModalOpen(true)}
            className="group relative bg-white dark:bg-slate-900 rounded-3xl p-8 shadow-sm border border-slate-200/60 dark:border-slate-800 hover:border-blue-500/50 hover:shadow-2xl hover:-translate-y-1 transition-all duration-300 cursor-pointer overflow-hidden"
          >
            <div className="absolute -right-10 -bottom-10 w-40 h-40 bg-blue-500/10 rounded-full blur-2xl group-hover:bg-blue-500/20 transition-all" />
            <div className="p-4 rounded-2xl bg-blue-50 dark:bg-blue-950/80 text-blue-600 dark:text-blue-400 w-fit mb-6 group-hover:scale-110 transition-transform shadow-sm">
              <UploadCloud className="w-8 h-8" />
            </div>
            <h3 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2 font-heading group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
              Upload Research Paper
            </h3>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 leading-relaxed mb-6">
              Drop PDFs to generate instant embeddings, chunk text, and index documents for semantic search.
            </p>
            <div className="inline-flex items-center gap-2 text-xs font-bold text-blue-600 dark:text-blue-400 group-hover:translate-x-1 transition-transform">
              Upload PDF Now <ArrowUpRight className="w-4 h-4" />
            </div>
          </div>

          {/* Card 2: New AI Chat */}
          <Link
            href="/chat"
            className="group relative bg-white dark:bg-slate-900 rounded-3xl p-8 shadow-sm border border-slate-200/60 dark:border-slate-800 hover:border-emerald-500/50 hover:shadow-2xl hover:-translate-y-1 transition-all duration-300 cursor-pointer overflow-hidden block"
          >
            <div className="absolute -right-10 -bottom-10 w-40 h-40 bg-emerald-500/10 rounded-full blur-2xl group-hover:bg-emerald-500/20 transition-all" />
            <div className="p-4 rounded-2xl bg-emerald-50 dark:bg-emerald-950/80 text-emerald-600 dark:text-emerald-400 w-fit mb-6 group-hover:scale-110 transition-transform shadow-sm">
              <MessageSquare className="w-8 h-8" />
            </div>
            <h3 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2 font-heading group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">
              New AI Chat Session
            </h3>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 leading-relaxed mb-6">
              Converse with your research papers in natural language with inline citations and RAG synthesis.
            </p>
            <div className="inline-flex items-center gap-2 text-xs font-bold text-emerald-600 dark:text-emerald-400 group-hover:translate-x-1 transition-transform">
              Start Conversation <ArrowUpRight className="w-4 h-4" />
            </div>
          </Link>

          {/* Card 3: Academic Search */}
          <Link
            href="/search"
            className="group relative bg-white dark:bg-slate-900 rounded-3xl p-8 shadow-sm border border-slate-200/60 dark:border-slate-800 hover:border-purple-500/50 hover:shadow-2xl hover:-translate-y-1 transition-all duration-300 cursor-pointer overflow-hidden block"
          >
            <div className="absolute -right-10 -bottom-10 w-40 h-40 bg-purple-500/10 rounded-full blur-2xl group-hover:bg-purple-500/20 transition-all" />
            <div className="p-4 rounded-2xl bg-purple-50 dark:bg-purple-950/80 text-purple-600 dark:text-purple-400 w-fit mb-6 group-hover:scale-110 transition-transform shadow-sm">
              <Compass className="w-8 h-8" />
            </div>
            <h3 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2 font-heading group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors">
              Academic Search
            </h3>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 leading-relaxed mb-6">
              Perform hybrid BM25 keyword matching and 768-dim vector retrieval across all uploaded files.
            </p>
            <div className="inline-flex items-center gap-2 text-xs font-bold text-purple-600 dark:text-purple-400 group-hover:translate-x-1 transition-transform">
              Launch Search <ArrowUpRight className="w-4 h-4" />
            </div>
          </Link>
        </section>

        {/* ── TWO-COLUMN MAIN CONTENT (DOCUMENTS + SIDEBAR) ──────────────────── */}
        <div className="flex flex-col xl:flex-row gap-8 items-start">
          {/* LEFT COLUMN: Documents & Conversations */}
          <div className="flex-1 w-full space-y-10">
            {/* ── RESEARCH DOCUMENTS SECTION ─────────────────────────────────── */}
            <section className="bg-white dark:bg-slate-900 rounded-3xl p-6 sm:p-8 shadow-sm border border-slate-200/60 dark:border-slate-800/80 space-y-6">
              {/* Documents Header & Controls */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100 dark:border-slate-800">
                <div>
                  <h3 className="text-xl font-bold text-slate-900 dark:text-slate-100 font-heading flex items-center gap-2">
                    <FileText className="w-5 h-5 text-blue-600" /> Research Documents ({documents.length})
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Indexed PDFs and vector collections in ChromaDB
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  {/* Search filter input */}
                  <div className="relative flex-1 sm:w-64">
                    <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      placeholder="Filter papers..."
                      value={searchFilter}
                      onChange={(e) => setSearchFilter(e.target.value)}
                      className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-800 dark:text-slate-200 placeholder-slate-400 focus:ring-2 focus:ring-blue-500 outline-none"
                    />
                  </div>

                  {/* Grid / List toggle */}
                  <div className="flex items-center p-1 rounded-xl bg-slate-100 dark:bg-slate-800">
                    <button
                      onClick={() => setViewMode('grid')}
                      className={`p-1.5 rounded-lg text-slate-500 transition-all ${
                        viewMode === 'grid' ? 'bg-white dark:bg-slate-900 text-blue-600 shadow-sm' : ''
                      }`}
                    >
                      <Grid className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setViewMode('list')}
                      className={`p-1.5 rounded-lg text-slate-500 transition-all ${
                        viewMode === 'list' ? 'bg-white dark:bg-slate-900 text-blue-600 shadow-sm' : ''
                      }`}
                    >
                      <List className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Documents Display */}
              {isLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="p-5 rounded-2xl border border-slate-100 dark:border-slate-800 space-y-3">
                      <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-3/4 animate-pulse"></div>
                      <div className="h-3 bg-slate-100 dark:bg-slate-800/60 rounded w-1/2 animate-pulse"></div>
                    </div>
                  ))}
                </div>
              ) : filteredDocs.length === 0 ? (
                /* EMPTY STATE */
                <div className="text-center py-12 px-4 rounded-3xl bg-slate-50/60 dark:bg-slate-950/40 border border-dashed border-slate-200 dark:border-slate-800 space-y-4">
                  <div className="w-20 h-20 mx-auto rounded-3xl bg-gradient-to-tr from-blue-500 to-purple-600 flex items-center justify-center text-white shadow-xl shadow-blue-500/20">
                    <FileText className="w-10 h-10" />
                  </div>
                  <div>
                    <h4 className="text-base font-bold text-slate-800 dark:text-slate-200">No research documents found</h4>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-sm mx-auto">
                      {searchFilter ? `No papers match "${searchFilter}".` : 'Upload your first PDF document to unlock vector analysis and RAG answers.'}
                    </p>
                  </div>
                  <button
                    onClick={() => setIsUploadModalOpen(true)}
                    className="px-6 py-2.5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 shadow-md shadow-blue-500/20 inline-flex items-center gap-2"
                  >
                    <Plus className="w-4 h-4" /> Upload Research Paper
                  </button>
                </div>
              ) : viewMode === 'grid' ? (
                /* GRID VIEW */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {filteredDocs.map((doc) => (
                    <div
                      key={doc.id}
                      className="group p-5 rounded-2xl bg-slate-50/70 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-800 hover:bg-white dark:hover:bg-slate-800 hover:shadow-xl hover:border-blue-500/40 transition-all duration-300 flex flex-col justify-between"
                    >
                      <div className="space-y-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-center gap-3 min-w-0">
                            <div className="p-3 rounded-xl bg-blue-100 dark:bg-blue-950 text-blue-600 dark:text-blue-400 group-hover:scale-105 transition-transform flex-shrink-0">
                              <FileText className="w-6 h-6" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100 truncate group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                                {doc.filename}
                              </h4>
                              <p className="text-[11px] text-slate-400 mt-0.5">
                                {(doc.file_size / (1024 * 1024)).toFixed(2)} MB • {new Date(doc.upload_timestamp).toLocaleDateString()}
                              </p>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 pt-1 text-xs">
                          <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                            doc.processing_status === 'completed'
                              ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-600 border border-emerald-200 dark:border-emerald-800'
                              : doc.processing_status === 'failed'
                              ? 'bg-red-50 dark:bg-red-950 text-red-600'
                              : 'bg-amber-50 dark:bg-amber-950 text-amber-600 animate-pulse'
                          }`}>
                            {doc.processing_status}
                          </span>
                          {doc.page_count && (
                            <span className="text-slate-500 dark:text-slate-400 text-[11px]">
                              {doc.page_count} pages
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Card Quick Actions */}
                      <div className="mt-5 pt-3 border-t border-slate-200/60 dark:border-slate-700/60 flex items-center justify-between gap-2">
                        <button
                          onClick={() => router.push(`/chat?document_id=${doc.id}`)}
                          className="px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold flex items-center gap-1.5 shadow-sm shadow-blue-500/20"
                        >
                          <MessageSquare className="w-3.5 h-3.5" /> Chat
                        </button>

                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => setSelectedDocForView(doc)}
                            className="p-1.5 text-slate-500 hover:text-slate-900 dark:hover:text-slate-100 rounded-lg hover:bg-slate-200/60 dark:hover:bg-slate-700"
                            title="View preview"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setSelectedDocForRename(doc)}
                            className="p-1.5 text-slate-500 hover:text-slate-900 dark:hover:text-slate-100 rounded-lg hover:bg-slate-200/60 dark:hover:bg-slate-700"
                            title="Rename"
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteDocument(doc.id, doc.filename)}
                            className="p-1.5 text-slate-400 hover:text-red-600 rounded-lg hover:bg-red-50 dark:hover:bg-red-950/40"
                            title="Delete"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                /* LIST VIEW */
                <div className="divide-y divide-slate-100 dark:divide-slate-800 border border-slate-200/60 dark:border-slate-800 rounded-2xl overflow-hidden">
                  {filteredDocs.map((doc) => (
                    <div
                      key={doc.id}
                      className="p-4 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors flex items-center justify-between gap-4"
                    >
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <div className="p-2.5 rounded-xl bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400 flex-shrink-0">
                          <FileText className="w-5 h-5" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100 truncate">
                            {doc.filename}
                          </h4>
                          <p className="text-[11px] text-slate-400">
                            {doc.page_count ? `${doc.page_count} pages • ` : ''}{(doc.file_size / (1024 * 1024)).toFixed(2)} MB • {new Date(doc.upload_timestamp).toLocaleDateString()}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 flex-shrink-0">
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                          doc.processing_status === 'completed'
                            ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-600'
                            : 'bg-amber-50 dark:bg-amber-950 text-amber-600'
                        }`}>
                          {doc.processing_status}
                        </span>
                        <button
                          onClick={() => router.push(`/chat?document_id=${doc.id}`)}
                          className="px-3 py-1.5 rounded-xl bg-blue-600 text-white text-xs font-bold"
                        >
                          Chat
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* ── RECENT AI CONVERSATIONS SECTION ─────────────────────────────── */}
            <section className="bg-white dark:bg-slate-900 rounded-3xl p-6 sm:p-8 shadow-sm border border-slate-200/60 dark:border-slate-800/80 space-y-6">
              <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800">
                <div>
                  <h3 className="text-xl font-bold text-slate-900 dark:text-slate-100 font-heading flex items-center gap-2">
                    <MessageSquare className="w-5 h-5 text-purple-600" /> Recent Conversations ({conversations.length})
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Resume previous research sessions and AI synthesis
                  </p>
                </div>
                <Link
                  href="/chat"
                  className="text-xs font-bold text-purple-600 dark:text-purple-400 hover:underline flex items-center gap-1"
                >
                  View All <ChevronRight className="w-3.5 h-3.5" />
                </Link>
              </div>

              {conversations.length === 0 ? (
                <p className="text-xs text-slate-400 italic text-center py-6">No recent conversations yet. Click "New AI Chat" above to begin!</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {conversations.slice(0, 4).map((chat) => (
                    <div
                      key={chat.id}
                      className="p-5 rounded-2xl bg-slate-50/70 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-800 hover:bg-white dark:hover:bg-slate-800 hover:shadow-lg transition-all space-y-3 flex flex-col justify-between"
                    >
                      <div>
                        <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100 truncate">
                          {chat.title || 'Untitled Session'}
                        </h4>
                        <p className="text-[11px] text-slate-400 mt-1">
                          {chat.message_count ? `${chat.message_count} messages` : 'Active thread'} • {new Date(chat.updated_at || chat.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      <Link
                        href={`/chat?session_id=${chat.id}`}
                        className="w-fit px-3 py-1.5 rounded-xl bg-purple-50 dark:bg-purple-950 text-purple-600 dark:text-purple-400 text-xs font-bold flex items-center gap-1 hover:bg-purple-100 dark:hover:bg-purple-900 transition-colors"
                      >
                        Continue Chat <ChevronRight className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          {/* RIGHT COLUMN: Sidebar Widgets (Activity, Notes, Goals) */}
          <SidebarRight documents={documents} />
        </div>
      </main>

      {/* ── MODALS ATTACHED ─────────────────────────────────────────────────── */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        documents={documents}
        onOpenUpload={() => setIsUploadModalOpen(true)}
      />

      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUploadSuccess={(newDoc) => {
          setDocuments((prev) => [newDoc, ...prev])
        }}
      />

      <DocumentViewModal
        document={selectedDocForView}
        onClose={() => setSelectedDocForView(null)}
      />

      <RenameModal
        document={selectedDocForRename}
        onClose={() => setSelectedDocForRename(null)}
        onRenameSuccess={handleRenameSuccess}
      />
    </div>
  )
}
