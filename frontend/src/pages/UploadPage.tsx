import { useState, useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Upload,
  FileText,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertCircle,
  RefreshCw,
  Clock,
  Trash2,
  ShieldAlert,
} from 'lucide-react';
import { uploadDocument, getDocuments, deleteDocument, ApiRequestError } from '../api/client';
import { Document } from '../api/types';
import { useApiError } from '../hooks/useApiError';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';

// =============================================================================
// File Validation - First Line of Defense (Client-Side)
// =============================================================================

/**
 * Allowed file extensions (must match backend DANGEROUS_EXTENSIONS blacklist inverse)
 * This is the first line of defense - backend validates again
 */
const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.txt', '.md', '.csv', '.json'];

/**
 * MIME types for accept attribute
 */
const ALLOWED_MIME_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/msword',
  'text/plain',
  'text/markdown',
  'text/csv',
  'application/json',
].join(',');

/**
 * Accept attribute value for file input
 * Combines extensions and MIME types for maximum compatibility
 */
const FILE_ACCEPT = `${ALLOWED_EXTENSIONS.join(',')},${ALLOWED_MIME_TYPES}`;

/**
 * Validate file extension on client-side
 * Returns error message if invalid, null if valid
 */
function validateFileExtension(filename: string): string | null {
  const ext = filename.toLowerCase().split('.').pop();
  if (!ext) {
    return 'Datei hat keine Erweiterung';
  }

  const isAllowed = ALLOWED_EXTENSIONS.some(
    (allowed) => allowed.toLowerCase() === `.${ext}`
  );

  if (!isAllowed) {
    return `Dateityp .${ext} ist nicht erlaubt. Erlaubt: ${ALLOWED_EXTENSIONS.join(', ')}`;
  }

  return null;
}

// =============================================================================
// Component
// =============================================================================

export default function UploadPage() {
  const [isDragging, setIsDragging] = useState(false);
  const [clientValidationError, setClientValidationError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const { showError, showSuccess, parseError } = useApiError();

  const {
    data: documents = [],
    isLoading: isLoadingDocs,
    refetch,
  } = useQuery({
    queryKey: ['documents'],
    queryFn: getDocuments,
    refetchInterval: 10000,
  });

  const uploadMutation = useMutation({
    mutationFn: uploadDocument,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      // Show success toast with filename
      if (data.message?.includes('duplicate')) {
        showSuccess(`"${data.filename}" bereits vorhanden (Duplikat erkannt)`);
      } else {
        showSuccess(`"${data.filename}" erfolgreich hochgeladen!`);
      }
    },
    onError: (error) => {
      // Error is automatically parsed by interceptor
      showError(error);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      showSuccess('Dokument erfolgreich gelöscht!');
    },
    onError: (error) => {
      showError(error);
    },
  });

  const handleDelete = (doc: Document) => {
    if (
      confirm(
        `Möchtest du "${doc.filename}" wirklich löschen?\n\nDies entfernt auch alle zugehörigen Vektoren und Graph-Knoten.`
      )
    ) {
      deleteMutation.mutate(doc.id);
    }
  };

  /**
   * Process files with client-side validation
   */
  const processFiles = useCallback(
    (files: File[]) => {
      setClientValidationError(null);

      for (const file of files) {
        // Client-side validation (first line of defense)
        const validationError = validateFileExtension(file.name);
        if (validationError) {
          setClientValidationError(validationError);
          showError(new Error(validationError), validationError);
          continue; // Skip this file, try others
        }

        // Upload file - backend will validate again
        uploadMutation.mutate(file);
      }
    },
    [uploadMutation, showError]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const files = Array.from(e.dataTransfer.files);
      processFiles(files);
    },
    [processFiles]
  );

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      processFiles(Array.from(files));
    }
    e.target.value = '';
  };

  /**
   * Get error details for display
   */
  const getUploadErrorDetails = () => {
    if (!uploadMutation.error) return null;

    const apiError = parseError(uploadMutation.error);

    return {
      message: apiError.message,
      type: apiError.type,
      isSecurityError: apiError.type === 'security',
      isValidationError: apiError.type === 'validation',
    };
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'INDEXED':
        return (
          <Badge variant="default" className="bg-green-500/20 text-green-400 border-green-500/30">
            <CheckCircle2 className="mr-1 h-3 w-3" />
            Indexiert
          </Badge>
        );
      case 'PROCESSING':
        return (
          <Badge variant="secondary" className="bg-aurora-400/20 text-aurora-400 border-aurora-400/30">
            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
            Verarbeitung...
          </Badge>
        );
      case 'PENDING':
        return (
          <Badge variant="outline" className="text-muted-foreground">
            <Clock className="mr-1 h-3 w-3" />
            Wartend
          </Badge>
        );
      case 'ERROR':
        return (
          <Badge variant="destructive" className="bg-red-500/20 text-red-400 border-red-500/30">
            <XCircle className="mr-1 h-3 w-3" />
            Fehler
          </Badge>
        );
      default:
        return (
          <Badge variant="outline">
            {status}
          </Badge>
        );
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const errorDetails = getUploadErrorDetails();

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="px-6 py-4 border-b border-border bg-card/50">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
              <Upload className="h-6 w-6 text-aurora-400" />
              Dokumente hochladen
            </h1>
            <p className="text-sm text-muted-foreground">
              Lade PDF, DOCX, TXT oder Markdown Dateien hoch
            </p>
          </div>

          <Button
            variant="outline"
            onClick={() => refetch()}
            disabled={isLoadingDocs}
          >
            <RefreshCw className={`h-4 w-4 ${isLoadingDocs ? 'animate-spin' : ''}`} />
            Aktualisieren
          </Button>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Upload Zone Card */}
          <Card
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`relative border-2 border-dashed transition-all duration-200 ${
              isDragging
                ? 'border-aurora-400 bg-aurora-400/10'
                : 'border-border hover:border-muted-foreground/50'
            }`}
          >
            <CardContent className="p-12">
              {/* File input with accept attribute for first-line defense */}
              <input
                type="file"
                id="file-upload"
                multiple
                accept={FILE_ACCEPT}
                onChange={handleFileSelect}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />

              <div className="flex flex-col items-center text-center">
                <div
                  className={`h-16 w-16 rounded-2xl flex items-center justify-center mb-4 ${
                    isDragging ? 'bg-aurora-400/20' : 'bg-muted'
                  }`}
                >
                  {uploadMutation.isPending ? (
                    <Loader2 className="h-8 w-8 text-aurora-400 animate-spin" />
                  ) : (
                    <Upload
                      className={`h-8 w-8 ${
                        isDragging ? 'text-aurora-400' : 'text-muted-foreground'
                      }`}
                    />
                  )}
                </div>

                <h3 className="text-lg font-semibold text-foreground mb-2">
                  {uploadMutation.isPending
                    ? 'Wird hochgeladen...'
                    : isDragging
                    ? 'Dateien hier ablegen'
                    : 'Dateien hochladen'}
                </h3>

                <p className="text-muted-foreground mb-4">
                  Ziehe Dateien hierher oder klicke zum Auswählen
                </p>

                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <FileText className="h-4 w-4" />
                  <span>PDF, DOCX, TXT, MD, CSV, JSON</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Client-Side Validation Error */}
          {clientValidationError && (
            <Alert variant="destructive" className="border-orange-500/30 bg-orange-500/10">
              <ShieldAlert className="h-4 w-4 text-orange-400" />
              <AlertTitle className="text-orange-400">Ungültiger Dateityp</AlertTitle>
              <AlertDescription className="text-orange-300">
                {clientValidationError}
              </AlertDescription>
            </Alert>
          )}

          {/* Upload Error with detailed message */}
          {uploadMutation.isError && errorDetails && (
            <Alert
              variant="destructive"
              className={`${
                errorDetails.isSecurityError
                  ? 'border-orange-500/30 bg-orange-500/10'
                  : 'border-red-500/30 bg-red-500/10'
              }`}
            >
              {errorDetails.isSecurityError ? (
                <ShieldAlert className="h-4 w-4 text-orange-400" />
              ) : (
                <AlertCircle className="h-4 w-4" />
              )}
              <AlertTitle className={errorDetails.isSecurityError ? 'text-orange-400' : ''}>
                {errorDetails.isSecurityError
                  ? 'Sicherheitsprüfung fehlgeschlagen'
                  : errorDetails.isValidationError
                  ? 'Validierungsfehler'
                  : 'Fehler beim Hochladen'}
              </AlertTitle>
              <AlertDescription className={errorDetails.isSecurityError ? 'text-orange-300' : ''}>
                {errorDetails.message}
              </AlertDescription>
            </Alert>
          )}

          {/* Delete Error */}
          {deleteMutation.isError && (
            <Alert variant="destructive" className="border-red-500/30 bg-red-500/10">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Fehler beim Löschen:{' '}
                {deleteMutation.error instanceof ApiRequestError
                  ? deleteMutation.error.apiError.message
                  : deleteMutation.error instanceof Error
                  ? deleteMutation.error.message
                  : 'Unbekannter Fehler'}
              </AlertDescription>
            </Alert>
          )}

          {/* Documents List Card */}
          <Card>
            <CardHeader>
              <CardTitle>Hochgeladene Dokumente</CardTitle>
              <CardDescription>
                {documents.length === 0
                  ? 'Noch keine Dokumente hochgeladen'
                  : `${documents.length} Dokument${documents.length !== 1 ? 'e' : ''} in der Wissensbasis`}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoadingDocs ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-aurora-400" />
                </div>
              ) : documents.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  Lade Dokumente hoch, um sie hier zu sehen
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Dateiname</TableHead>
                      <TableHead>Größe</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Hochgeladen</TableHead>
                      <TableHead className="text-right">Aktionen</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {documents.map((doc: Document) => (
                      <TableRow key={doc.id}>
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <FileText className="h-5 w-5 text-muted-foreground" />
                            <span className="font-medium">{doc.filename}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {formatFileSize(doc.file_size)}
                        </TableCell>
                        <TableCell>
                          <div className="space-y-1">
                            {getStatusBadge(doc.status)}
                            {doc.error_message && (
                              <p className="text-xs text-destructive">
                                {doc.error_message}
                              </p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {formatDate(doc.created_at)}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDelete(doc)}
                            disabled={deleteMutation.isPending}
                            className="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                          >
                            {deleteMutation.isPending &&
                            deleteMutation.variables === doc.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Trash2 className="h-4 w-4" />
                            )}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
