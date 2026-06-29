import React, { useEffect, useState } from 'react'
import { X, FileText, Calendar, HardDrive, Layers, Sparkles, CheckCircle2, AlertCircle, Clock, MessageSquare } from 'lucide-react'
import { apiClient, DocumentResponse } from '@/lib/api'
import { useRouter } from 'next/router'
import toast from 'react-hot-toast'

interface DocumentViewModalProps {
  document: DocumentResponse | null
  onClose: () => void
}

export default function DocumentViewModal({ document, onClose }: DocumentViewModalProps) {
  const router = useRouter()
  const [details, setDetails] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (document) {
      setLoading(true)
      apiClient.getDocument(document.id)
        .then(res => setDetails(res))
        .catch(() => setDetails(null))
        .finally(() => setLoading(false))
    }
  }, [document])

  if (!document) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200/80 dark:border-slate-800 w-full max-w-2xl overflow-hidden transform transition-all p-6">
        <div className="flex items-start justify-between pb-4 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-3.5">
            <div className="p-3 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 text-white shadow-md shadow-blue-500/20">
              <FileText className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100 truncate max-w-md">
                {document.filename}
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                ID: {document.id}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="mt-6 space-y-6">
          {/* Info grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
                <Layers className="w-3.5 h-3.5" /> Pages
              </div>
              <p className="text-sm font-bold text-slate-800 dark:text-slate-200">
                {document.page_count ?? 'N/A'} Pages
              </p>
            </div>
            <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
                <HardDrive className="w-3.5 h-3.5" /> Size
              </div>
              <p className="text-sm font-bold text-slate-800 dark:text-slate-200">
                {(document.file_size / (1024 * 1024)).toFixed(2)} MB
              </p>
            </div>
            <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
                <Calendar className="w-3.5 h-3.5" /> Uploaded
              </div>
              <p className="text-sm font-bold text-slate-800 dark:text-slate-200">
                {new Date(document.upload_timestamp).toLocaleDateString()}
              </p>
            </div>
            <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
                <Clock className="w-3.5 h-3.5" /> Status
              </div>
              <span className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full ${
                document.processing_status === 'completed'
                  ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400'
                  : 'bg-amber-50 dark:bg-amber-950 text-amber-600 dark:text-amber-400'
              }`}>
                {document.processing_status}
              </span>
            </div>
          </div>

          {/* Text Preview / Content */}
          <div>
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Extracted Content Preview
            </h4>
            <div className="p-4 rounded-2xl bg-slate-900 text-slate-200 text-xs font-mono max-h-48 overflow-y-auto leading-relaxed border border-slate-800">
              {loading ? (
                <div className="animate-pulse space-y-2">
                  <div className="h-4 bg-slate-800 rounded w-3/4"></div>
                  <div className="h-4 bg-slate-800 rounded w-full"></div>
                  <div className="h-4 bg-slate-800 rounded w-5/6"></div>
                </div>
              ) : details?.text_preview || details?.extracted_text ? (
                <p className="whitespace-pre-wrap">{details.text_preview || details.extracted_text}</p>
              ) : (
                <p className="text-slate-500 italic">No text preview available for this document.</p>
              )}
            </div>
          </div>
        </div>

        {/* Modal actions */}
        <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-sm font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            Close
          </button>
          <button
            onClick={() => {
              onClose()
              router.push(`/chat?document_id=${document.id}`)
            }}
            className="px-5 py-2.5 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 shadow-md shadow-blue-500/20 flex items-center gap-2"
          >
            <MessageSquare className="w-4 h-4" /> Start AI Chat
          </button>
        </div>
      </div>
    </div>
  )
}
