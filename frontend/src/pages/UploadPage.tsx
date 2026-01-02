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
    refetchInterval: 10000, // Refresh every 10 seconds to see status updates
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
    // Reset input
    e.target.value = '';
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'INDEXED':
        return <CheckCircle2 className="w-5 h-5 text-green-400" />;
      case 'PROCESSING':
      case 'PENDING':
        return <Loader2 className="w-5 h-5 text-aurora-400 animate-spin" />;
      case 'ERROR':
        return <XCircle className="w-5 h-5 text-red-400" />;
      default:
        return <Clock className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'INDEXED':
        return 'Indexiert';
      case 'PROCESSING':
        return 'Verarbeitung...';
      case 'PENDING':
        return 'Wartend';
      case 'ERROR':
        return 'Fehler';
      default:
        return status;
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
      <header className="px-6 py-4 border-b border-midnight-800 bg-midnight-900/50">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-white flex items-center gap-2">
              <Upload className="w-6 h-6 text-aurora-400" />
              Dokumente hochladen
            </h1>
            <p className="text-sm text-gray-400">
              Lade PDF, DOCX oder TXT Dateien hoch
            </p>
          </div>

          <button
            onClick={() => refetch()}
            disabled={isLoadingDocs}
            className="px-4 py-2 bg-midnight-800 hover:bg-midnight-700 text-gray-300 rounded-lg transition-colors flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${isLoadingDocs ? 'animate-spin' : ''}`} />
            <span>Aktualisieren</span>
          </button>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-4xl mx-auto space-y-8">
          {/* Upload Zone */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`relative border-2 border-dashed rounded-2xl p-12 text-center transition-all duration-200 ${
              isDragging
                ? 'border-aurora-400 bg-aurora-400/10'
                : 'border-midnight-700 hover:border-midnight-600 bg-midnight-900/50'
            }`}
          >
            <input
              type="file"
              id="file-upload"
              multiple
              accept=".pdf,.docx,.txt,.md"
              onChange={handleFileSelect}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            />

            <div className="flex flex-col items-center">
              <div
                className={`w-16 h-16 rounded-2xl flex items-center justify-center mb-4 ${
                  isDragging ? 'bg-aurora-400/20' : 'bg-midnight-800'
                }`}
              >
                {uploadMutation.isPending ? (
                  <Loader2 className="w-8 h-8 text-aurora-400 animate-spin" />
                ) : (
                  <Upload
                    className={`w-8 h-8 ${
                      isDragging ? 'text-aurora-400' : 'text-gray-400'
                    }`}
                  />
                )}
              </div>

              <h3 className="text-lg font-semibold text-white mb-2">
                {uploadMutation.isPending
                  ? 'Wird hochgeladen...'
                  : isDragging
                  ? 'Dateien hier ablegen'
                  : 'Dateien hochladen'}
              </h3>

              <p className="text-gray-400 mb-4">
                Ziehe Dateien hierher oder klicke zum Auswählen
              </p>

              <div className="flex items-center gap-2 text-sm text-gray-500">
                <FileText className="w-4 h-4" />
                <span>PDF, DOCX, TXT, MD</span>
              </div>
            </div>
          </div>

          {/* Upload Status */}
          {uploadMutation.isSuccess && (
            <div className="flex items-center gap-3 p-4 bg-green-500/10 border border-green-500/30 rounded-xl">
              <CheckCircle2 className="w-5 h-5 text-green-400" />
              <span className="text-green-400">Datei erfolgreich hochgeladen!</span>
            </div>
          )}

          {uploadMutation.isError && (
            <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/30 rounded-xl">
              <AlertCircle className="w-5 h-5 text-red-400" />
              <span className="text-red-400">
                Fehler beim Hochladen:{' '}
                {uploadMutation.error instanceof Error
                  ? uploadMutation.error.message
                  : 'Unbekannter Fehler'}
              </span>
            </div>
          )}

          {deleteMutation.isSuccess && (
            <div className="flex items-center gap-3 p-4 bg-green-500/10 border border-green-500/30 rounded-xl">
              <CheckCircle2 className="w-5 h-5 text-green-400" />
              <span className="text-green-400">Dokument erfolgreich gelöscht!</span>
            </div>
          )}

          {deleteMutation.isError && (
            <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/30 rounded-xl">
              <AlertCircle className="w-5 h-5 text-red-400" />
              <span className="text-red-400">
                Fehler beim Löschen:{' '}
                {deleteMutation.error instanceof Error
                  ? deleteMutation.error.message
                  : 'Unbekannter Fehler'}
              </span>
            </div>
          )}

          {/* Documents List */}
          <div>
            <h2 className="text-lg font-semibold text-white mb-4">
              Hochgeladene Dokumente
            </h2>

            {isLoadingDocs ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-aurora-400" />
              </div>
            ) : documents.length === 0 ? (
              <div className="text-center py-12 text-gray-400">
                Noch keine Dokumente hochgeladen
              </div>
            ) : (
              <div className="bg-midnight-900/50 rounded-xl border border-midnight-800 overflow-hidden">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-midnight-800">
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-400">
                        Dateiname
                      </th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-400">
                        Größe
                      </th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-400">
                        Status
                      </th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-400">
                        Hochgeladen
                      </th>
                      <th className="px-4 py-3 text-right text-sm font-medium text-gray-400">
                        Aktionen
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {documents.map((doc: Document) => (
                      <tr
                        key={doc.id}
                        className="border-b border-midnight-800/50 hover:bg-midnight-800/30 transition-colors"
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <FileText className="w-5 h-5 text-gray-400" />
                            <span className="text-white font-medium">
                              {doc.filename}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-gray-400">
                          {formatFileSize(doc.file_size)}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            {getStatusIcon(doc.status)}
                            <span
                              className={`text-sm ${
                                doc.status === 'ERROR'
                                  ? 'text-red-400'
                                  : doc.status === 'INDEXED'
                                  ? 'text-green-400'
                                  : 'text-gray-400'
                              }`}
                            >
                              {getStatusText(doc.status)}
                            </span>
                          </div>
                          {doc.error_message && (
                            <p className="text-xs text-red-400 mt-1">
                              {doc.error_message}
                            </p>
                          )}
                        </td>
                        <td className="px-4 py-3 text-gray-400 text-sm">
                          {formatDate(doc.created_at)}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => handleDelete(doc)}
                            disabled={deleteMutation.isPending}
                            className="p-2 text-gray-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors disabled:opacity-50"
                            title="Dokument löschen"
                          >
                            {deleteMutation.isPending &&
                            deleteMutation.variables === doc.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Trash2 className="w-4 h-4" />
                            )}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
