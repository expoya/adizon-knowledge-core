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
} from 'lucide-react';
import { uploadDocument, getDocuments, deleteDocument } from '../api/client';
import { Document } from '../api/types';

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
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';

export default function UploadPage() {
  const [isDragging, setIsDragging] = useState(false);
  const queryClient = useQueryClient();

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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
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
      files.forEach((file) => {
        uploadMutation.mutate(file);
      });
    },
    [uploadMutation]
  );

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      Array.from(files).forEach((file) => {
        uploadMutation.mutate(file);
      });
    }
    e.target.value = '';
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
              Lade PDF, DOCX oder TXT Dateien hoch
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
              <input
                type="file"
                id="file-upload"
                multiple
                accept=".pdf,.docx,.txt,.md"
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
                  <span>PDF, DOCX, TXT, MD</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Upload Status Alerts */}
          {uploadMutation.isSuccess && (
            <Alert className="border-green-500/30 bg-green-500/10">
              <CheckCircle2 className="h-4 w-4 text-green-400" />
              <AlertDescription className="text-green-400">
                Datei erfolgreich hochgeladen!
              </AlertDescription>
            </Alert>
          )}

          {uploadMutation.isError && (
            <Alert variant="destructive" className="border-red-500/30 bg-red-500/10">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Fehler beim Hochladen:{' '}
                {uploadMutation.error instanceof Error
                  ? uploadMutation.error.message
                  : 'Unbekannter Fehler'}
              </AlertDescription>
            </Alert>
          )}

          {deleteMutation.isSuccess && (
            <Alert className="border-green-500/30 bg-green-500/10">
              <CheckCircle2 className="h-4 w-4 text-green-400" />
              <AlertDescription className="text-green-400">
                Dokument erfolgreich gelöscht!
              </AlertDescription>
            </Alert>
          )}

          {deleteMutation.isError && (
            <Alert variant="destructive" className="border-red-500/30 bg-red-500/10">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Fehler beim Löschen:{' '}
                {deleteMutation.error instanceof Error
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
