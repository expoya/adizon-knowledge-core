/**
 * API Client for Adizon Knowledge Core Backend
 */

import axios, { AxiosInstance } from 'axios';
import {
  ChatRequest,
  ChatResponse,
  Document,
  UploadResponse,
  GraphNode,
  GraphQueryRequest,
  GraphQueryResponse,
  KnowledgeSummary,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Create axios instance with default config
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// =============================================================================
// Chat API
// =============================================================================

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  const response = await apiClient.post<ChatResponse>('/chat', request);
  return response.data;
}

// =============================================================================
// Document API
// =============================================================================

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post<UploadResponse>('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
}

export async function getDocuments(): Promise<Document[]> {
  const response = await apiClient.get<Document[]>('/documents');
  return response.data;
}

export async function reprocessDocument(documentId: string): Promise<void> {
  await apiClient.post(`/documents/${documentId}/reprocess`);
}

export interface DeleteDocumentResponse {
  id: string;
  filename: string;
  vectors_deleted: boolean;
  graph_nodes_deleted: number;
  storage_deleted: boolean;
  message: string;
}

export async function deleteDocument(documentId: string): Promise<DeleteDocumentResponse> {
  const response = await apiClient.delete<DeleteDocumentResponse>(`/documents/${documentId}`);
  return response.data;
}

// =============================================================================
// Graph API
// =============================================================================

export async function executeGraphQuery(request: GraphQueryRequest): Promise<GraphQueryResponse> {
  const response = await apiClient.post<GraphQueryResponse>('/graph/query', request);
  return response.data;
}

interface PendingNodesResponse {
  nodes: GraphNode[];
  count: number;
}

export async function getPendingNodes(): Promise<GraphNode[]> {
  const response = await apiClient.get<PendingNodesResponse>('/graph/pending');
  return response.data.nodes.map((node) => ({
    ...node,
    status: 'PENDING' as const,
  }));
}

export async function approveNodes(nodeIds: string[]): Promise<void> {
  await apiClient.post('/graph/approve', { node_ids: nodeIds });
}

export async function rejectNodes(nodeIds: string[]): Promise<void> {
  await apiClient.post('/graph/reject', { node_ids: nodeIds });
}

// =============================================================================
// Knowledge Summary API
// =============================================================================

export async function getKnowledgeSummary(): Promise<KnowledgeSummary> {
  const response = await apiClient.get<KnowledgeSummary>('/knowledge/summary');
  return response.data;
}

export { apiClient };
