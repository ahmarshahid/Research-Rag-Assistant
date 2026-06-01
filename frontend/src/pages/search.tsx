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
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <Link
            href="/dashboard"
            className="flex items-center gap-2 text-slate-600 hover:text-slate-900 transition-colors"
          >
            <FiArrowLeft /> Back to Dashboard
          </Link>
          <h1 className="text-2xl font-bold text-slate-900">Document Search</h1>
          <div />
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Search form */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-8">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Select Document
              </label>
              {isLoading ? (
                <div className="text-slate-600">Loading documents...</div>
              ) : documents.length === 0 ? (
                <div className="text-slate-600">No documents available</div>
              ) : (
                <select
                  value={selectedDoc}
                  onChange={(e) => setSelectedDoc(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg"
                >
                  {documents.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.filename} ({doc.page_count} pages)
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Search Type Selector - Phase 8 */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Search Type (Phase 8 Advanced Retrieval)
              </label>
              <div className="grid grid-cols-3 gap-2">
                {(['semantic', 'bm25', 'hybrid'] as const).map((type) => (
                  <button
                    key={type}
                    onClick={() => setSearchType(type)}
                    className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      searchType === type
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                    }`}
                  >
                    {type === 'semantic' && '🔍 Semantic'}
                    {type === 'bm25' && '📝 BM25'}
                    {type === 'hybrid' && '⚡ Hybrid (Recommended)'}
                  </button>
                ))}
              </div>
              <p className="text-xs text-slate-500 mt-2">
                {searchType === 'semantic' && 'Meaning-based search using embeddings'}
                {searchType === 'bm25' && 'Keyword-based search using BM25 algorithm'}
                {searchType === 'hybrid' && 'Combined semantic + keyword + reranking (best results)'}
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Search Query
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                  placeholder="What are you looking for?"
                  className="flex-1 px-3 py-2 border border-slate-300 rounded-lg"
                />
                <button
                  onClick={handleSearch}
                  disabled={isSearching || !selectedDoc}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  <FiSearch /> {isSearching ? 'Searching...' : 'Search'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Search Stats - Phase 8 */}
        {searchTime > 0 && (
          <div className="bg-slate-100 rounded-lg p-3 mb-6 text-sm text-slate-600">
            <span className="font-medium">Search completed in {searchTime}ms</span>
            <span className="ml-4">Method: {searchType.toUpperCase()}</span>
          </div>
        )}

        {/* Results */}
        {results.length > 0 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-slate-900">
              Results ({results.length})
            </h2>
            {results.map((result, idx) => (
              <div key={idx} className="bg-white rounded-lg shadow-sm p-6 border-l-4 border-blue-500">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="font-medium text-slate-900">Result #{idx + 1}</h3>
                    {result.page_number && (
                      <p className="text-xs text-slate-600">Page {result.page_number}</p>
                    )}
                  </div>
                  <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
                    {searchType.toUpperCase()}
                  </span>
                </div>

                <p className="text-slate-700 mb-4 line-clamp-3">
                  {result.text || result.text_preview || result.content}
                </p>

                {/* Phase 8: Show all scores */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3 text-xs">
                  {result.semantic_score !== undefined && (
                    <div className="bg-slate-50 p-2 rounded">
                      <span className="text-slate-600">Semantic</span>
                      <p className="font-semibold">{(result.semantic_score * 100).toFixed(0)}%</p>
                    </div>
                  )}
                  {result.bm25_score !== undefined && (
                    <div className="bg-slate-50 p-2 rounded">
                      <span className="text-slate-600">BM25</span>
                      <p className="font-semibold">{(result.bm25_score * 100).toFixed(0)}%</p>
                    </div>
                  )}
                  {result.rerank_score !== undefined && (
                    <div className="bg-slate-50 p-2 rounded">
                      <span className="text-slate-600">Rerank</span>
                      <p className="font-semibold">{(result.rerank_score * 100).toFixed(0)}%</p>
                    </div>
                  )}
                  {result.hybrid_score !== undefined && (
                    <div className="bg-slate-50 p-2 rounded">
                      <span className="text-slate-600">Hybrid</span>
                      <p className="font-semibold text-blue-600">{(result.hybrid_score * 100).toFixed(0)}%</p>
                    </div>
                  )}
                  {result.score !== undefined && (
                    <div className="bg-slate-50 p-2 rounded">
                      <span className="text-slate-600">Score</span>
                      <p className="font-semibold">{result.score.toFixed(1)}</p>
                    </div>
                  )}
                  {result.similarity_score !== undefined && (
                    <div className="bg-slate-50 p-2 rounded">
                      <span className="text-slate-600">Similarity</span>
                      <p className="font-semibold">{(result.similarity_score * 100).toFixed(0)}%</p>
                    </div>
                  )}
                </div>

                {result.source && (
                  <div className="text-xs text-slate-500 mb-3">
                    Source: {result.source}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {query && results.length === 0 && !isSearching && (
          <div className="text-center text-slate-600 py-8">
            <p>No results found for "{query}"</p>
            <p className="text-sm mt-2">Try different search terms or switch search type</p>
          </div>
        )}
      </main>
    </div>
  )
}
