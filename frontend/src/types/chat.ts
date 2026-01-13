/**
 * Chat Types for Adizon Knowledge Core
 */

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  sources?: string[]
  graph_context?: string
  vector_context?: string
}

export interface Chat {
  id: string
  name: string
  messages: ChatMessage[]
  createdAt: number
  updatedAt: number
}
