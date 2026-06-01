import { useEffect, useState } from 'react'
import { useRouter } from 'next/router'
import Link from 'next/link'
import { useAuthStore } from '@/lib/auth-store'
import { apiClient, DocumentResponse } from '@/lib/api'
import toast from 'react-hot-toast'
import { FiUpload, FiMessageSquare, FiSearch, FiLogOut } from 'react-icons/fi'

export default function DashboardPage() {
  const router = useRouter()
  const { user, logout, checkAuth } = useAuthStore()
  const [documents, setDocuments] = useState<DocumentResponse[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    const init = async () => {
      await checkAuth()
      if (!user) {
        router.push('/auth/login')
        return
      }
      loadDocuments()
    }
    init()
  }, [])

  const loadDocuments = async () => {
    try {
      const docs = await apiClient.listDocuments()
      setDocuments(docs)
    } catch {
      toast.error('Failed to load documents')
    } finally {
      setIsLoading(false)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    try {
      await apiClient.uploadDocument(file)
      toast.success('Document uploaded successfully!')
      await loadDocuments()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const handleLogout = async () => {
    await logout()
    router.push('/auth/login')
  }

  if (!user) return null

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-slate-900">AI Research Assistant</h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-slate-600">{user.email}</span>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 text-slate-600 hover:text-slate-900 transition-colors"
            >
              <FiLogOut />
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Quick actions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <label className="bg-white rounded-lg shadow-sm p-6 hover:shadow-md transition-shadow cursor-pointer border-2 border-dashed border-blue-300 hover:border-blue-500">
            <input
              type="file"
              accept=".pdf"
              onChange={handleFileUpload}
              disabled={uploading}
              className="hidden"
            />
            <div className="text-center">
              <FiUpload className="w-8 h-8 text-blue-600 mx-auto mb-2" />
              <p className="font-medium text-slate-900">Upload PDF</p>
              <p className="text-sm text-slate-600 mt-1">
                {uploading ? 'Uploading...' : 'Click to upload'}
              </p>
            </div>
          </label>

          <Link
            href="/chat"
            className="bg-white rounded-lg shadow-sm p-6 hover:shadow-md transition-shadow border-2 border-slate-200 hover:border-green-300"
          >
            <div className="text-center">
              <FiMessageSquare className="w-8 h-8 text-green-600 mx-auto mb-2" />
              <p className="font-medium text-slate-900">New Chat</p>
              <p className="text-sm text-slate-600 mt-1">Start conversation</p>
            </div>
          </Link>

          <Link
            href="/search"
            className="bg-white rounded-lg shadow-sm p-6 hover:shadow-md transition-shadow border-2 border-slate-200 hover:border-purple-300"
          >
            <div className="text-center">
              <FiSearch className="w-8 h-8 text-purple-600 mx-auto mb-2" />
              <p className="font-medium text-slate-900">Search</p>
              <p className="text-sm text-slate-600 mt-1">Find information</p>
            </div>
          </Link>
        </div>

        {/* Documents list */}
        <div className="bg-white rounded-lg shadow-sm">
          <div className="px-6 py-4 border-b border-slate-200">
            <h2 className="text-lg font-semibold text-slate-900">
              Documents ({documents.length})
            </h2>
          </div>

          {isLoading ? (
            <div className="px-6 py-8 text-center text-slate-600">Loading...</div>
          ) : documents.length === 0 ? (
            <div className="px-6 py-8 text-center text-slate-600">
              No documents uploaded yet. Upload one to get started!
            </div>
          ) : (
            <div className="divide-y divide-slate-200">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="px-6 py-4 hover:bg-slate-50 transition-colors cursor-pointer"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <h3 className="font-medium text-slate-900">{doc.filename}</h3>
                      <div className="flex gap-4 mt-1 text-sm text-slate-600">
                        <span>{doc.page_count} pages</span>
                        <span>
                          Status:{' '}
                          <span
                            className={
                              doc.processing_status === 'completed'
                                ? 'text-green-600'
                                : doc.processing_status === 'failed'
                                  ? 'text-red-600'
                                  : 'text-yellow-600'
                            }
                          >
                            {doc.processing_status}
                          </span>
                        </span>
                      </div>
                    </div>
                    <Link
                      href={`/documents/${doc.id}`}
                      className="text-blue-600 hover:text-blue-700 font-medium"
                    >
                      View
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
