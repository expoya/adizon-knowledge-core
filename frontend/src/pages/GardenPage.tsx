import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Flower2,
  Check,
  X,
  RefreshCw,
  AlertCircle,
  FileText,
  Loader2,
  CheckCircle2,
} from 'lucide-react';
import { getPendingNodes, approveNodes, rejectNodes } from '../api/client';
import { GraphNode } from '../api/types';

export default function GardenPage() {
  const [selectedNodes, setSelectedNodes] = useState<Set<string>>(new Set());
  const queryClient = useQueryClient();

  const {
    data: nodes = [],
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['pendingNodes'],
    queryFn: getPendingNodes,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const approveMutation = useMutation({
    mutationFn: (nodeIds: string[]) => approveNodes(nodeIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pendingNodes'] });
      setSelectedNodes(new Set());
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (nodeIds: string[]) => rejectNodes(nodeIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pendingNodes'] });
      setSelectedNodes(new Set());
    },
  });

  const toggleNode = (nodeId: string) => {
    setSelectedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedNodes.size === nodes.length) {
      setSelectedNodes(new Set());
    } else {
      setSelectedNodes(new Set(nodes.map((n) => n.id)));
    }
  };

  const handleApprove = () => {
    if (selectedNodes.size === 0) return;
    approveMutation.mutate(Array.from(selectedNodes));
  };

  const handleReject = () => {
    if (selectedNodes.size === 0) return;
    if (
      confirm(
        `Möchtest du wirklich ${selectedNodes.size} Knoten löschen? Diese Aktion kann nicht rückgängig gemacht werden.`
      )
    ) {
      rejectMutation.mutate(Array.from(selectedNodes));
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return '-';
    try {
      return new Date(dateString).toLocaleString('de-DE', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateString;
    }
  };

  const getTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      Organization: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
      Person: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
      Product: 'bg-green-500/20 text-green-400 border-green-500/30',
      Service: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
      Location: 'bg-red-500/20 text-red-400 border-red-500/30',
      Concept: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
      Event: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
    };
    return colors[type] || 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="px-6 py-4 border-b border-midnight-800 bg-midnight-900/50">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-white flex items-center gap-2">
              <Flower2 className="w-6 h-6 text-aurora-400" />
              Wissens-Garten
            </h1>
            <p className="text-sm text-gray-400">
              Prüfe und genehmige extrahierte Entitäten
            </p>
          </div>

          <button
            onClick={() => refetch()}
            disabled={isLoading}
            className="px-4 py-2 bg-midnight-800 hover:bg-midnight-700 text-gray-300 rounded-lg transition-colors flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Aktualisieren</span>
          </button>
        </div>
      </header>

      {/* Toolbar */}
      <div className="px-6 py-3 border-b border-midnight-800 bg-midnight-900/30 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-400">
            {selectedNodes.size} von {nodes.length} ausgewählt
          </span>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleApprove}
            disabled={selectedNodes.size === 0 || approveMutation.isPending}
            className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-midnight-700 disabled:text-gray-500 text-white rounded-lg transition-colors flex items-center gap-2"
          >
            {approveMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Check className="w-4 h-4" />
            )}
            <span>Freigeben</span>
          </button>

          <button
            onClick={handleReject}
            disabled={selectedNodes.size === 0 || rejectMutation.isPending}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-midnight-700 disabled:text-gray-500 text-white rounded-lg transition-colors flex items-center gap-2"
          >
            {rejectMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <X className="w-4 h-4" />
            )}
            <span>Ablehnen</span>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-8 h-8 animate-spin text-aurora-400" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <AlertCircle className="w-12 h-12 text-red-400 mb-4" />
            <h2 className="text-lg font-semibold text-white mb-2">Fehler beim Laden</h2>
            <p className="text-gray-400">
              {error instanceof Error ? error.message : 'Unbekannter Fehler'}
            </p>
          </div>
        ) : nodes.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <CheckCircle2 className="w-12 h-12 text-green-400 mb-4" />
            <h2 className="text-lg font-semibold text-white mb-2">Alles erledigt!</h2>
            <p className="text-gray-400">
              Keine Entitäten warten auf Freigabe.
            </p>
          </div>
        ) : (
          <div className="bg-midnight-900/50 rounded-xl border border-midnight-800 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-midnight-800">
                  <th className="px-4 py-3 text-left">
                    <input
                      type="checkbox"
                      checked={selectedNodes.size === nodes.length && nodes.length > 0}
                      onChange={toggleAll}
                      className="w-4 h-4 rounded border-midnight-600 bg-midnight-800 text-aurora-500 focus:ring-aurora-400 focus:ring-offset-0"
                    />
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-400">
                    Typ
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-400">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-400">
                    Quelle
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-400">
                    Erstellt
                  </th>
                </tr>
              </thead>
              <tbody>
                {nodes.map((node: GraphNode) => (
                  <tr
                    key={node.id}
                    className={`border-b border-midnight-800/50 hover:bg-midnight-800/30 transition-colors ${
                      selectedNodes.has(node.id) ? 'bg-midnight-800/50' : ''
                    }`}
                  >
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selectedNodes.has(node.id)}
                        onChange={() => toggleNode(node.id)}
                        className="w-4 h-4 rounded border-midnight-600 bg-midnight-800 text-aurora-500 focus:ring-aurora-400 focus:ring-offset-0"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-1 text-xs font-medium rounded border ${getTypeColor(
                          node.type
                        )}`}
                      >
                        {node.type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-white font-medium">{node.name}</td>
                    <td className="px-4 py-3">
                      {node.source_file ? (
                        <span className="flex items-center gap-2 text-gray-400 text-sm">
                          <FileText className="w-4 h-4" />
                          {node.source_file}
                        </span>
                      ) : (
                        <span className="text-gray-500">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-sm">
                      {formatDate(node.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
