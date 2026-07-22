import { useEffect, useState } from 'react'
import { useRouter } from 'next/router'
import Link from 'next/link'
import { useAuthStore } from '@/lib/auth-store'
import { apiClient, DocumentResponse, SearchResult } from '@/lib/api'
import toast from 'react-hot-toast'
import { FiSearch, FiArrowLeft } from 'react-icons/fi'

type SearchType = 'semantic' | 'bm25' | 'hybrid'

export default function SearchPage() {
  const router = useRouter()
  const { user, checkAuth } = useAuthStore()
  const [documents, setDocuments] = useState<DocumentResponse[]>([])
  const [selectedDoc, setSelectedDoc] = useState<string>('')
  const [query, setQuery] = useState('')
  const [searchType, setSearchType] = useState<SearchType>('hybrid')
  const [results, setResults] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSearching, setIsSearching] = useState(false)
  const [searchTime, setSearchTime] = useState<number>(0)

  useEffect(() => {
    const init = async () => {
      await checkAuth()
      if (!user) {
        router.push('/auth/login')
        return
      }
      await loadDocuments()
    }
    init()
  }, [])

  const loadDocuments = async () => {
    try {
      const docs = await apiClient.listDocuments()
      setDocuments(docs)
      if (docs.length > 0) {
        setSelectedDoc(docs[0].id)
      }
    } catch {
      toast.error('Failed to load documents')
    } finally {
      setIsLoading(false)
    }
  }

  const handleSearch = async () => {
    if (!selectedDoc || !query.trim()) {
      toast.error('Please select a document and enter a query')
      return
    }

    setIsSearching(true)
    const startTime = Date.now()
    try {
      let searchResults: any[] = []
      let searchMetadata: any = {}

      switch (searchType) {
        case 'semantic':
          searchResults = await apiClient.searchDocuments(selectedDoc, query, 10)
          break
        case 'bm25':
          const bm25Result = await apiClient.bm25Search(selectedDoc, query, 10)
          searchResults = bm25Result.results
          searchMetadata = bm25Result
          break
        case 'hybrid':
          const hybridResult = await apiClient.hybridSearch(selectedDoc, query, 10)
          searchResults = hybridResult.results
          searchMetadata = hybridResult
          break
      }

      setResults(searchResults)
      const elapsed = Date.now() - startTime
      setSearchTime(elapsed)
      
      if (searchResults.length === 0) {
        toast('No results found', { icon: '🔍' })
      } else {
        toast.success(`Found ${searchResults.length} results in ${elapsed}ms`, {
          duration: 3000,
        })
      }
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Search failed')
    } finally {
      setIsSearching(false)
    }
  }

  if (!user) return null

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0f0c29] via-[#302b63] to-[#24243e] text-slate-200 font-sans selection:bg-indigo-500/30">
      {/* Header */}
      <header className="bg-black/20 backdrop-blur-md border-b border-white/10 sticky top-0 z-50">
        <div className="max-w-[90rem] mx-auto px-4 sm:px-6 lg:px-8 py-5 flex justify-between items-center">
          <Link
            href="/dashboard"
            className="flex items-center gap-2 text-indigo-300 hover:text-white transition-colors text-sm font-medium"
          >
            <FiArrowLeft /> Back to Dashboard
          </Link>
          <h1 className="text-2xl font-bold text-white tracking-tight">Document Search</h1>
          <div className="w-32" /> {/* Spacer for centering */}
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-[90rem] mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* LEFT COLUMN: Search Form */}
          <div className="lg:col-span-4 lg:sticky lg:top-28 space-y-6">
            <div className="bg-white/5 backdrop-blur-md border border-white/10 rounded-3xl shadow-2xl p-6 relative overflow-hidden">
              <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[120%] h-1/2 bg-indigo-500/20 blur-[100px] pointer-events-none" />

              <div className="space-y-6 relative z-10">
                {/* Select Document */}
                <div>
                  <label className="block text-sm font-medium text-indigo-200 mb-2">
                    Select Document
                  </label>
                  {isLoading ? (
                    <div className="text-indigo-300/70 animate-pulse text-sm">Loading documents...</div>
                  ) : documents.length === 0 ? (
                    <div className="text-indigo-300/70 text-sm">No documents available</div>
                  ) : (
                    <div className="relative">
                      <select
                        value={selectedDoc}
                        onChange={(e) => setSelectedDoc(e.target.value)}
                        className="w-full px-4 py-3.5 bg-black/40 border border-white/10 rounded-xl text-white appearance-none focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all shadow-inner text-sm"
                      >
                        {documents.map((doc) => (
                          <option key={doc.id} value={doc.id} className="bg-[#1e1b4b] text-white">
                            {doc.filename} ({doc.page_count} pages)
                          </option>
                        ))}
                      </select>
                      <div className="absolute inset-y-0 right-0 flex items-center px-4 pointer-events-none text-indigo-300">
                        <svg className="w-4 h-4 fill-current" viewBox="0 0 20 20"><path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" fillRule="evenodd"></path></svg>
                      </div>
                    </div>
                  )}
                </div>

                {/* Search Engine */}
                <div>
                  <label className="block text-sm font-medium text-indigo-200 mb-2">
                    Search Engine
                  </label>
                  <div className="flex flex-col gap-3">
                    {(['semantic', 'bm25', 'hybrid'] as const).map((type) => (
                      <button
                        key={type}
                        onClick={() => setSearchType(type)}
                        className={`px-4 py-3 rounded-xl text-sm font-medium transition-all duration-300 flex justify-between items-center ${
                          searchType === type
                            ? 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white shadow-[0_0_20px_rgba(99,102,241,0.4)] border border-transparent scale-[1.02]'
                            : 'bg-white/5 text-indigo-200 hover:bg-white/10 border border-white/5 hover:text-white'
                        }`}
                      >
                        <span className="flex items-center gap-2">
                          {type === 'semantic' && '🔍 Semantic'}
                          {type === 'bm25' && '📝 BM25'}
                          {type === 'hybrid' && '⚡ Hybrid (Best)'}
                        </span>
                        {searchType === type && (
                          <div className="w-2 h-2 rounded-full bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)]" />
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Query Input */}
                <div className="pt-2">
                  <label className="block text-sm font-medium text-indigo-200 mb-2">
                    Search Query
                  </label>
                  <div className="flex flex-col gap-3">
                    <input
                      type="text"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                      placeholder="What are you looking for?"
                      className="w-full px-4 py-4 bg-black/40 border border-white/10 rounded-xl text-white placeholder-indigo-300/40 focus:outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 transition-all shadow-inner"
                    />
                    <button
                      onClick={handleSearch}
                      disabled={isSearching || !selectedDoc}
                      className="w-full bg-white text-indigo-900 hover:bg-indigo-50 px-6 py-4 rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 font-bold shadow-xl"
                    >
                      <FiSearch className={isSearching ? 'animate-pulse' : ''} /> 
                      {isSearching ? 'Searching...' : 'Search Document'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* RIGHT COLUMN: Results */}
          <div className="lg:col-span-8 space-y-6">
            
            {/* Search Stats */}
            {searchTime > 0 && (
              <div className="bg-white/5 border border-indigo-500/20 backdrop-blur-sm rounded-xl p-4 text-sm text-indigo-200 flex flex-wrap items-center justify-between gap-4 shadow-lg">
                <span className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)] animate-pulse" />
                  Completed in <strong className="text-white">{searchTime}ms</strong>
                </span>
                <span className="flex items-center gap-2 bg-black/30 px-3 py-1 rounded-md text-xs font-mono uppercase tracking-wider text-indigo-300 border border-white/5">
                  {searchType} Engine
                </span>
              </div>
            )}

            {/* Results List */}
            {results.length > 0 && (
              <div className="space-y-6">
                <h2 className="text-xl font-bold text-white flex items-center gap-3">
                  Results 
                  <span className="bg-indigo-500/20 text-indigo-300 text-sm px-3 py-1 rounded-full border border-indigo-500/30">
                    {results.length} found
                  </span>
                </h2>
                
                <div className="grid grid-cols-1 gap-6">
                  {results.map((result, idx) => (
                    <div key={idx} className="bg-white/5 backdrop-blur-md rounded-2xl p-6 md:p-8 border border-white/10 hover:border-indigo-500/40 transition-colors group relative overflow-hidden shadow-xl">
                      {/* Accent bar */}
                      <div className="absolute top-0 left-0 w-1.5 h-full bg-gradient-to-b from-indigo-400 to-purple-600 opacity-80 group-hover:opacity-100 transition-opacity" />
                      
                      <div className="flex flex-col sm:flex-row justify-between items-start mb-5 gap-3">
                        <div>
                          <h3 className="font-semibold text-white text-lg flex items-center gap-2">
                            Result #{idx + 1}
                          </h3>
                          {result.page_number && (
                            <p className="text-sm text-indigo-300 mt-1 flex items-center gap-1.5">
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                              Page {result.page_number}
                            </p>
                          )}
                        </div>
                        <span className="text-[11px] font-bold tracking-widest uppercase bg-indigo-500/10 text-indigo-300 px-4 py-1.5 rounded-full border border-indigo-500/20">
                          {searchType}
                        </span>
                      </div>

                      <div className="bg-black/20 rounded-xl p-5 mb-6 border border-white/5 shadow-inner">
                        <p className="text-slate-300 text-base leading-relaxed line-clamp-4">
                          {result.text || result.text_preview || result.content}
                        </p>
                      </div>

                      {/* Score Pills */}
                      <div className="flex flex-wrap gap-2.5 text-xs">
                        {result.semantic_score !== undefined && (
                          <div className="bg-white/5 border border-white/10 px-3 py-1.5 rounded-lg flex items-center gap-2 hover:bg-white/10 transition-colors">
                            <span className="text-indigo-300/70">Semantic</span>
                            <span className="text-white font-semibold">{(result.semantic_score * 100).toFixed(0)}%</span>
                          </div>
                        )}
                        {result.bm25_score !== undefined && (
                          <div className="bg-white/5 border border-white/10 px-3 py-1.5 rounded-lg flex items-center gap-2 hover:bg-white/10 transition-colors">
                            <span className="text-indigo-300/70">BM25</span>
                            <span className="text-white font-semibold">{(result.bm25_score * 100).toFixed(0)}%</span>
                          </div>
                        )}
                        {result.rerank_score !== undefined && (
                          <div className="bg-white/5 border border-white/10 px-3 py-1.5 rounded-lg flex items-center gap-2 hover:bg-white/10 transition-colors">
                            <span className="text-indigo-300/70">Rerank</span>
                            <span className="text-white font-semibold">{(result.rerank_score * 100).toFixed(0)}%</span>
                          </div>
                        )}
                        {result.hybrid_score !== undefined && (
                          <div className="bg-indigo-500/20 border border-indigo-500/30 px-4 py-1.5 rounded-lg flex items-center gap-2">
                            <span className="text-indigo-300">Hybrid Match</span>
                            <span className="text-white font-bold">{(result.hybrid_score * 100).toFixed(0)}%</span>
                          </div>
                        )}
                        {result.score !== undefined && (
                          <div className="bg-white/5 border border-white/10 px-3 py-1.5 rounded-lg flex items-center gap-2">
                            <span className="text-indigo-300/70">Score</span>
                            <span className="text-white font-semibold">{result.score.toFixed(2)}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Empty State / Not found */}
            {query && results.length === 0 && !isSearching && (
              <div className="text-center py-20 bg-white/5 backdrop-blur-md rounded-3xl border border-white/10 shadow-xl relative overflow-hidden h-full flex flex-col items-center justify-center">
                 <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[80%] h-[80%] bg-indigo-500/5 blur-[100px] pointer-events-none" />
                <div className="w-20 h-20 bg-white/5 rounded-full flex items-center justify-center mx-auto mb-6 relative z-10 border border-white/10">
                  <FiSearch className="w-10 h-10 text-indigo-400/50" />
                </div>
                <p className="text-white font-bold text-xl mb-3 relative z-10">No results found for "{query}"</p>
                <p className="text-indigo-300/70 text-base relative z-10">Try using different keywords or switch the search engine</p>
              </div>
            )}
            
            {/* Initial empty state (before searching) */}
            {!query && results.length === 0 && !isSearching && (
              <div className="text-center py-20 bg-white/5 backdrop-blur-md rounded-3xl border border-white/10 shadow-xl relative overflow-hidden h-[50vh] flex flex-col items-center justify-center">
                <div className="w-20 h-20 bg-white/5 rounded-full flex items-center justify-center mx-auto mb-6 border border-white/10">
                  <FiSearch className="w-10 h-10 text-indigo-400/30" />
                </div>
                <p className="text-white/60 font-medium text-lg">Enter a query on the left to begin searching.</p>
              </div>
            )}
            
          </div>
        </div>
      </main>
    </div>
  )
}
