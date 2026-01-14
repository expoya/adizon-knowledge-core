/**
 * API Client for Adizon Knowledge Core Backend
 *
 * Features:
 * - Axios instance with response interceptors
 * - Centralized error handling
 * - TypeScript interfaces for all endpoints
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import {
  ChatRequest,
  ChatResponse,
  Document,
  UploadResponse,
  GraphQueryRequest,
  GraphQueryResponse,
  KnowledgeSummary,
} from './types';
import { parseApiError, ApiError } from './errors';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Create axios instance with default config
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second timeout
});

// =============================================================================
// Custom Error Class
// =============================================================================

/**
 * Custom error class that includes parsed API error information.
 * Use with: error instanceof ApiRequestError
 */
export class ApiRequestError extends Error {
  public readonly apiError: ApiError;

  constructor(apiError: ApiError) {
    super(apiError.message);
    this.name = 'ApiRequestError';
    this.apiError = apiError;
  }
}

// =============================================================================
// Response Interceptor - Global Error Handling
// =============================================================================

/**
 * Response interceptor for centralized error handling.
 *
 * Transforms backend errors into normalized ApiError objects:
 * - HTTP 422: Pydantic validation errors with field details
 * - HTTP 400/403: Business logic and security errors
 * - HTTP 503: Service unavailable warnings
 * - Network errors: Connection issues
 */
apiClient.interceptors.response.use(
  // Success handler - pass through
  (response) => response,

  // Error handler - parse and transform
  (error: AxiosError) => {
    const apiError = parseApiError(error);

    // Log errors for debugging (only in development)
    if (import.meta.env.DEV) {
      console.error('[API Error]', {
        status: apiError.status,
        type: apiError.type,
        message: apiError.message,
        field: apiError.field,
        url: error.config?.url,
      });
    }

    // Throw a custom error with the parsed information
    throw new ApiRequestError(apiError);
  }
);

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

// =============================================================================
// Knowledge Summary API
// =============================================================================

export async function getKnowledgeSummary(): Promise<KnowledgeSummary> {
  const response = await apiClient.get<KnowledgeSummary>('/knowledge/summary');
  return response.data;
}

export { apiClient };
