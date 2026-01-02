import { useState, useRef, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  Send,
  Bot,
  User,
  ChevronDown,
  ChevronUp,
  FileText,
  Network,
  Loader2,
} from 'lucide-react';
import { sendChatMessage } from '../api/client';
import { ChatMessage, ChatResponse } from '../api/types';

interface MessageWithContext extends ChatMessage {
  sources?: string[];
  graph_context?: string;
  vector_context?: string;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<MessageWithContext[]>([]);
  const [input, setInput] = useState('');
  const [expandedMessages, setExpandedMessages] = useState<Set<number>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const chatMutation = useMutation({
    mutationFn: (message: string) => {
      const history = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));
      return sendChatMessage({ message, history });
    },
    onSuccess: (response: ChatResponse) => {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: response.answer,
          sources: response.sources,
          graph_context: response.graph_context,
          vector_context: response.vector_context,
        },
      ]);
    },
    onError: (error) => {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Fehler: ${error instanceof Error ? error.message : 'Unbekannter Fehler'}`,
        },
      ]);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || chatMutation.isPending) return;

    const userMessage = input.trim();
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setInput('');
    chatMutation.mutate(userMessage);
  };

  const toggleExpanded = (index: number) => {
    setExpandedMessages((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="px-6 py-4 border-b border-midnight-800 bg-midnight-900/50">
        <h1 className="text-xl font-semibold text-white">Chat</h1>
        <p className="text-sm text-gray-400">
          Frage dein Wissen ab - basierend auf Vektoren und Graph
        </p>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-2xl bg-midnight-800 flex items-center justify-center mb-4">
              <Bot className="w-8 h-8 text-aurora-400" />
            </div>
            <h2 className="text-xl font-semibold text-white mb-2">
              Willkommen bei Adizon Knowledge Core
            </h2>
            <p className="text-gray-400 max-w-md">
              Stelle eine Frage zu deiner Wissensbasis. Ich durchsuche Dokumente
              und den Knowledge Graph, um dir die beste Antwort zu geben.
            </p>
          </div>
        )}

        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex gap-4 ${
              message.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            {message.role === 'assistant' && (
              <div className="w-10 h-10 rounded-xl bg-midnight-800 flex items-center justify-center flex-shrink-0">
                <Bot className="w-5 h-5 text-aurora-400" />
              </div>
            )}

            <div
              className={`max-w-2xl ${
                message.role === 'user'
                  ? 'bg-midnight-600 rounded-2xl rounded-br-md'
                  : 'bg-midnight-800/50 rounded-2xl rounded-bl-md border border-midnight-700'
              } px-5 py-4`}
            >
              <p className="text-gray-100 whitespace-pre-wrap">{message.content}</p>

              {/* Context Details for Assistant */}
              {message.role === 'assistant' &&
                (message.sources?.length || message.graph_context) && (
                  <div className="mt-4 pt-3 border-t border-midnight-700">
                    <button
                      onClick={() => toggleExpanded(index)}
                      className="flex items-center gap-2 text-sm text-gray-400 hover:text-aurora-400 transition-colors"
                    >
                      {expandedMessages.has(index) ? (
                        <ChevronUp className="w-4 h-4" />
                      ) : (
                        <ChevronDown className="w-4 h-4" />
                      )}
                      <span>Quellen & Kontext anzeigen</span>
                    </button>

                    {expandedMessages.has(index) && (
                      <div className="mt-3 space-y-3">
                        {/* Sources */}
                        {message.sources && message.sources.length > 0 && (
                          <div>
                            <div className="flex items-center gap-2 text-sm font-medium text-gray-300 mb-2">
                              <FileText className="w-4 h-4" />
                              <span>Quellen</span>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              {message.sources.map((source, i) => (
                                <span
                                  key={i}
                                  className="px-2 py-1 text-xs bg-midnight-700 rounded-md text-gray-300"
                                >
                                  {source}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Graph Context */}
                        {message.graph_context &&
                          message.graph_context !== 'Keine Graph-Daten verfügbar.' && (
                            <div>
                              <div className="flex items-center gap-2 text-sm font-medium text-gray-300 mb-2">
                                <Network className="w-4 h-4" />
                                <span>Graph-Kontext</span>
                              </div>
                              <pre className="text-xs bg-midnight-900 rounded-lg p-3 overflow-x-auto text-gray-400">
                                {message.graph_context}
                              </pre>
                            </div>
                          )}
                      </div>
                    )}
                  </div>
                )}
            </div>

            {message.role === 'user' && (
              <div className="w-10 h-10 rounded-xl bg-midnight-600 flex items-center justify-center flex-shrink-0">
                <User className="w-5 h-5 text-gray-300" />
              </div>
            )}
          </div>
        ))}

        {chatMutation.isPending && (
          <div className="flex gap-4">
            <div className="w-10 h-10 rounded-xl bg-midnight-800 flex items-center justify-center">
              <Bot className="w-5 h-5 text-aurora-400" />
            </div>
            <div className="bg-midnight-800/50 rounded-2xl rounded-bl-md border border-midnight-700 px-5 py-4">
              <div className="flex items-center gap-2 text-gray-400">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Denke nach...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-midnight-800 bg-midnight-900/50">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Stelle eine Frage..."
              className="flex-1 px-4 py-3 bg-midnight-800 border border-midnight-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-aurora-400 focus:border-transparent transition-all"
              disabled={chatMutation.isPending}
            />
            <button
              type="submit"
              disabled={!input.trim() || chatMutation.isPending}
              className="px-6 py-3 bg-aurora-500 hover:bg-aurora-600 disabled:bg-midnight-700 disabled:text-gray-500 text-white font-medium rounded-xl transition-all duration-200 flex items-center gap-2"
            >
              <Send className="w-4 h-4" />
              <span>Senden</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
