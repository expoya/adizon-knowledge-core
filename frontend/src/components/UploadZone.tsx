import { useState, useCallback, DragEvent } from 'react'
import { Upload, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'

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

    e.target.value = ''
  }, [])

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h2 className="text-2xl font-semibold text-foreground">Upload Documents</h2>
        <p className="mt-1 text-muted-foreground">
          Drag and drop files to add them to your knowledge base
        </p>
      </div>

      {/* Drop Zone */}
      <Card
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed transition-all duration-300 ease-out
          ${state.isDragging
            ? 'border-aurora-400 bg-aurora-400/10 scale-[1.02]'
            : 'border-border hover:border-muted-foreground/50'
          }
          ${state.isUploading ? 'opacity-50 pointer-events-none' : ''}
        `}
      >
        <CardContent className="p-12">
          <div className="flex flex-col items-center text-center">
            {/* Icon */}
            <div className={`
              h-16 w-16 rounded-2xl mb-6 flex items-center justify-center
              transition-all duration-300
              ${state.isDragging
                ? 'bg-aurora-400/20 text-aurora-400 scale-110'
                : 'bg-muted text-muted-foreground'
              }
            `}>
              {state.isUploading ? (
                <Loader2 className="h-8 w-8 animate-spin" />
              ) : (
                <Upload className="h-8 w-8" />
              )}
            </div>

            {/* Text */}
            <h3 className="text-lg font-medium text-foreground mb-2">
              {state.isUploading ? 'Uploading...' : 'Drop files here'}
            </h3>
            <p className="text-muted-foreground mb-6">
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
            <Button asChild>
              <label htmlFor="file-upload" className="cursor-pointer">
                Select Files
              </label>
            </Button>

            {/* Supported formats */}
            <p className="mt-6 text-xs text-muted-foreground">
              Supported: PDF, DOCX, TXT, Markdown
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Status Messages */}
      {state.error && (
        <Alert variant="destructive" className="border-destructive/30 bg-destructive/10">
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      )}
      {state.success && (
        <Alert className="border-green-500/30 bg-green-500/10">
          <AlertDescription className="text-green-400">{state.success}</AlertDescription>
        </Alert>
      )}
    </div>
  )
}
