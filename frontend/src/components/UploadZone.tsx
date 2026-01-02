import { useState, useCallback, DragEvent } from 'react'

interface UploadState {
  isDragging: boolean
  isUploading: boolean
  error: string | null
  success: string | null
}

export default function UploadZone() {
  const [state, setState] = useState<UploadState>({
    isDragging: false,
    isUploading: false,
    error: null,
    success: null,
  })

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setState(prev => ({ ...prev, isDragging: true }))
  }, [])

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setState(prev => ({ ...prev, isDragging: false }))
  }, [])

  const handleDrop = useCallback(async (e: DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setState(prev => ({ ...prev, isDragging: false, isUploading: true, error: null, success: null }))

    const files = Array.from(e.dataTransfer.files)
    
    if (files.length === 0) {
      setState(prev => ({ ...prev, isUploading: false, error: 'No files dropped' }))
      return
    }

    try {
      for (const file of files) {
        const formData = new FormData()
        formData.append('file', file)

        const response = await fetch('/api/upload', {
          method: 'POST',
          body: formData,
        })

        if (!response.ok) {
          const error = await response.json()
          throw new Error(error.detail || 'Upload failed')
        }
      }

      setState(prev => ({
        ...prev,
        isUploading: false,
        success: `Successfully uploaded ${files.length} file(s)`,
      }))
    } catch (error) {
      setState(prev => ({
        ...prev,
        isUploading: false,
        error: error instanceof Error ? error.message : 'Upload failed',
      }))
    }
  }, [])

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    setState(prev => ({ ...prev, isUploading: true, error: null, success: null }))

    try {
      for (const file of Array.from(files)) {
        const formData = new FormData()
        formData.append('file', file)

        const response = await fetch('/api/upload', {
          method: 'POST',
          body: formData,
        })

        if (!response.ok) {
          const error = await response.json()
          throw new Error(error.detail || 'Upload failed')
        }
      }

      setState(prev => ({
        ...prev,
        isUploading: false,
        success: `Successfully uploaded ${files.length} file(s)`,
      }))
    } catch (error) {
      setState(prev => ({
        ...prev,
        isUploading: false,
        error: error instanceof Error ? error.message : 'Upload failed',
      }))
    }

    // Reset input
    e.target.value = ''
  }, [])

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h2 className="text-2xl font-semibold text-white">Upload Documents</h2>
        <p className="mt-1 text-gray-400">
          Drag and drop files to add them to your knowledge base
        </p>
      </div>

      {/* Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed rounded-2xl p-12
          transition-all duration-300 ease-out
          ${state.isDragging
            ? 'border-aurora-400 bg-aurora-400/10 scale-[1.02]'
            : 'border-midnight-700 hover:border-midnight-600 bg-midnight-900/50'
          }
          ${state.isUploading ? 'opacity-50 pointer-events-none' : ''}
        `}
      >
        <div className="flex flex-col items-center text-center">
          {/* Icon */}
          <div className={`
            w-16 h-16 rounded-2xl mb-6 flex items-center justify-center
            transition-all duration-300
            ${state.isDragging
              ? 'bg-aurora-400/20 text-aurora-400 scale-110'
              : 'bg-midnight-800 text-gray-400'
            }
          `}>
            {state.isUploading ? (
              <svg className="w-8 h-8 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            ) : (
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            )}
          </div>

          {/* Text */}
          <h3 className="text-lg font-medium text-white mb-2">
            {state.isUploading ? 'Uploading...' : 'Drop files here'}
          </h3>
          <p className="text-gray-500 mb-6">
            or click to browse your files
          </p>

          {/* Hidden File Input */}
          <input
            type="file"
            multiple
            onChange={handleFileSelect}
            className="hidden"
            id="file-upload"
            accept=".pdf,.doc,.docx,.txt,.md"
          />
          <label
            htmlFor="file-upload"
            className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg cursor-pointer transition-colors shadow-lg shadow-indigo-500/25"
          >
            Select Files
          </label>

          {/* Supported formats */}
          <p className="mt-6 text-xs text-gray-600">
            Supported: PDF, DOCX, TXT, Markdown
          </p>
        </div>
      </div>

      {/* Status Messages */}
      {state.error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400">
          {state.error}
        </div>
      )}
      {state.success && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-400">
          {state.success}
        </div>
      )}
    </div>
  )
}

