/**
 * API Types for Adizon Knowledge Core
 */

// Chat Types
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  message: string;
  history?: ChatMessage[];
}

export interface ChatResponse {
  answer: string;
  sources: string[];
  graph_context: string;
  vector_context: string;
}

// Document Types
export interface Document {
  id: string;
  filename: string;
  status: 'PENDING' | 'PROCESSING' | 'INDEXED' | 'ERROR';
  file_size: number;
  created_at: string;
  error_message?: string;
}

export interface UploadResponse {
  id: string;
  filename: string;
  status: string;
  message: string;
}

// Graph Types
export interface GraphQueryRequest {
  cypher: string;
  parameters?: Record<string, unknown>;
}

export interface GraphQueryResponse {
  records: Record<string, unknown>[];
  summary?: string;
}

// Knowledge Summary
export interface KnowledgeSummary {
  graph: string;
  status: string;
}
