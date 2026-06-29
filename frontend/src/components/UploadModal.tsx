import React, { useState } from 'react'
import { UploadCloud, X, FileText, CheckCircle2, AlertCircle, Sparkles, Loader2 } from 'lucide-react'
import { apiClient, DocumentResponse } from '@/lib/api'
import toast from 'react-hot-toast'

interface UploadModalProps {
  isOpen: boolean
  onClose: () => void
  onUploadSuccess: (doc: DocumentResponse) => void
}

export default function UploadModal({ isOpen, onClose, onUploadSuccess }: UploadModalProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)

  if (!isOpen) return null

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const selectedFile = e.dataTransfer.files[0]
      if (selectedFile.type === 'application/pdf' || selectedFile.name.endsWith('.pdf')) {
        setFile(selectedFile)
      } else {
        toast.error('Please upload a valid PDF document')
      }
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
    }
  }

  const handleStartUpload = async () => {
    if (!file) return
    setUploading(true)
    setProgress(20)

    const interval = setInterval(() => {
      setProgress((prev) => (prev < 90 ? prev + 15 : prev))
    }, 400)

    try {
      const doc = await apiClient.uploadDocument(file)
      clearInterval(interval)
      setProgress(100)
      toast.success('Research paper uploaded & indexed!')
      setTimeout(() => {
        onUploadSuccess(doc)
        setFile(null)
        setUploading(false)
        setProgress(0)
        onClose()
      }, 600)
    } catch (error: any) {
      clearInterval(interval)
      setUploading(false)
      setProgress(0)
      toast.error(error.response?.data?.detail || 'Failed to upload document')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200/80 dark:border-slate-800 w-full max-w-lg overflow-hidden transform transition-all p-6">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400">
              <UploadCloud className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                Upload Research Paper
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Process PDF for AI extraction & semantic search
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={uploading}
            className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Dropzone */}
        <div className="mt-6">
          {!file ? (
            <label
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`flex flex-col items-center justify-center p-8 border-2 border-dashed rounded-3xl cursor-pointer transition-all ${
                isDragging
                  ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-950/40 scale-[1.01]'
                  : 'border-slate-200 dark:border-slate-800 hover:border-blue-400 hover:bg-slate-50/80 dark:hover:bg-slate-800/40'
              }`}
            >
              <input
                type="file"
                accept=".pdf"
                onChange={handleFileChange}
                className="hidden"
              />
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-blue-500 to-purple-600 flex items-center justify-center text-white shadow-lg shadow-blue-500/30 mb-4 animate-bounce">
                <UploadCloud className="w-8 h-8" />
              </div>
              <p className="text-base font-semibold text-slate-800 dark:text-slate-200 text-center">
                Drag & drop your research PDF here
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 text-center">
                or click to browse from your computer (Max 50MB)
              </p>
              <div className="mt-4 flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-100 dark:bg-slate-800 text-xs font-medium text-slate-600 dark:text-slate-400">
                <Sparkles className="w-3.5 h-3.5 text-blue-500" /> Auto Vector Embeddings
              </div>
            </label>
          ) : (
            <div className="p-5 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/80 dark:border-slate-700/80">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="p-3 rounded-xl bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400">
                    <FileText className="w-6 h-6" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-bold text-slate-800 dark:text-slate-200 truncate">
                      {file.name}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {(file.size / (1024 * 1024)).toFixed(2)} MB • Ready for processing
                    </p>
                  </div>
                </div>
                {!uploading && (
                  <button
                    onClick={() => setFile(null)}
                    className="p-1.5 text-slate-400 hover:text-red-500 rounded-lg"
                  >
                    <X className="w-5 h-5" />
                  </button>
                )}
              </div>

              {uploading && (
                <div className="mt-4 space-y-2">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-600 dark:text-slate-300">
                    <span className="flex items-center gap-1.5">
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-500" /> Extracting & Indexing...
                    </span>
                    <span>{progress}%</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-500 to-purple-600 transition-all duration-300 rounded-full"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            disabled={uploading}
            className="px-4 py-2.5 rounded-xl text-sm font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            Cancel
          </button>
          {file && (
            <button
              onClick={handleStartUpload}
              disabled={uploading}
              className="px-6 py-2.5 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 shadow-md shadow-blue-500/20 flex items-center gap-2 transition-all"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> Processing...
                </>
              ) : (
                <>
                  <UploadCloud className="w-4 h-4" /> Start Upload
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
