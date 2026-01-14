import { useState, useCallback, DragEvent } from 'react'
import { Upload, Loader2, ShieldAlert } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { uploadDocument } from '../api/client'
import { useApiError } from '../hooks/useApiError'

// =============================================================================
// File Validation - First Line of Defense
// =============================================================================

const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.txt', '.md', '.csv', '.json'];

const ALLOWED_MIME_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/msword',
  'text/plain',
  'text/markdown',
  'text/csv',
  'application/json',
].join(',');

const FILE_ACCEPT = `${ALLOWED_EXTENSIONS.join(',')},${ALLOWED_MIME_TYPES}`;

function validateFileExtension(filename: string): string | null {
  const ext = filename.toLowerCase().split('.').pop();
  if (!ext) return 'Datei hat keine Erweiterung';

  const isAllowed = ALLOWED_EXTENSIONS.some(
    (allowed) => allowed.toLowerCase() === `.${ext}`
  );

  if (!isAllowed) {
    return `Dateityp .${ext} ist nicht erlaubt. Erlaubt: ${ALLOWED_EXTENSIONS.join(', ')}`;
  }

  return null;
}

// =============================================================================
// Component State
// =============================================================================

interface UploadState {
  isDragging: boolean
  isUploading: boolean
  error: string | null
  errorType: 'validation' | 'security' | 'general' | null
  success: string | null
}

// =============================================================================
// Component
// =============================================================================

export default function UploadZone() {
  const [state, setState] = useState<UploadState>({
    isDragging: false,
    isUploading: false,
    error: null,
    errorType: null,
    success: null,
  })

  const { showError, showSuccess, parseError } = useApiError()

  /**
   * Process files with client-side validation and API upload
   */
  const processFiles = useCallback(async (files: File[]) => {
    if (files.length === 0) {
      setState(prev => ({ ...prev, error: 'Keine Dateien ausgewählt', errorType: 'general' }))
      return
    }

    setState(prev => ({ ...prev, isUploading: true, error: null, errorType: null, success: null }))

    let successCount = 0
    let lastError: string | null = null
    let lastErrorType: 'validation' | 'security' | 'general' | null = null

    for (const file of files) {
      // Client-side validation
      const validationError = validateFileExtension(file.name)
      if (validationError) {
        lastError = validationError
        lastErrorType = 'validation'
        showError(new Error(validationError))
        continue
      }

      try {
        // Use the API client (with interceptor)
        const response = await uploadDocument(file)

        if (response.message?.includes('duplicate')) {
          showSuccess(`"${response.filename}" bereits vorhanden (Duplikat)`)
        } else {
          showSuccess(`"${response.filename}" hochgeladen!`)
        }
        successCount++
      } catch (error) {
        // Error is parsed by interceptor
        const apiError = parseError(error)
        lastError = apiError.message
        lastErrorType = apiError.type === 'security' ? 'security' : 'general'
        showError(error)
      }
    }

    if (successCount > 0 && !lastError) {
      setState(prev => ({
        ...prev,
        isUploading: false,
        success: `${successCount} Datei${successCount > 1 ? 'en' : ''} erfolgreich hochgeladen`,
      }))
    } else if (lastError) {
      setState(prev => ({
        ...prev,
        isUploading: false,
        error: lastError,
        errorType: lastErrorType,
        success: successCount > 0 ? `${successCount} Datei(en) hochgeladen` : null,
      }))
    } else {
      setState(prev => ({ ...prev, isUploading: false }))
    }
  }, [showError, showSuccess, parseError])

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
    setState(prev => ({ ...prev, isDragging: false }))

    const files = Array.from(e.dataTransfer.files)
    await processFiles(files)
  }, [processFiles])

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    await processFiles(Array.from(files))
    e.target.value = ''
  }, [processFiles])

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h2 className="text-2xl font-semibold text-foreground">Dokumente hochladen</h2>
        <p className="mt-1 text-muted-foreground">
          Ziehe Dateien hierher, um sie zur Wissensbasis hinzuzufügen
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
              {state.isUploading ? 'Wird hochgeladen...' : 'Dateien hier ablegen'}
            </h3>
            <p className="text-muted-foreground mb-6">
              oder klicken zum Auswählen
            </p>

            {/* Hidden File Input with accept attribute */}
            <input
              type="file"
              multiple
              onChange={handleFileSelect}
              className="hidden"
              id="file-upload-zone"
              accept={FILE_ACCEPT}
            />
            <Button asChild>
              <label htmlFor="file-upload-zone" className="cursor-pointer">
                Dateien auswählen
              </label>
            </Button>

            {/* Supported formats */}
            <p className="mt-6 text-xs text-muted-foreground">
              Erlaubt: PDF, DOCX, TXT, MD, CSV, JSON
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Status Messages */}
      {state.error && (
        <Alert
          variant="destructive"
          className={
            state.errorType === 'security' || state.errorType === 'validation'
              ? 'border-orange-500/30 bg-orange-500/10'
              : 'border-destructive/30 bg-destructive/10'
          }
        >
          {(state.errorType === 'security' || state.errorType === 'validation') && (
            <ShieldAlert className="h-4 w-4 text-orange-400" />
          )}
          <AlertTitle className={state.errorType === 'security' ? 'text-orange-400' : ''}>
            {state.errorType === 'security'
              ? 'Sicherheitsprüfung fehlgeschlagen'
              : state.errorType === 'validation'
              ? 'Ungültiger Dateityp'
              : 'Fehler beim Hochladen'}
          </AlertTitle>
          <AlertDescription className={state.errorType === 'security' ? 'text-orange-300' : ''}>
            {state.error}
          </AlertDescription>
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
