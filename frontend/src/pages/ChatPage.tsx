import { useRef, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import {
  Send,
  Bot,
  User,
  ChevronDown,
  ChevronUp,
  FileText,
  Network,
} from 'lucide-react'
import { sendChatMessage } from '../api/client'
import { ChatResponse } from '../api/types'
import { useChatStore } from '@/stores/chatStore'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { useState } from 'react'

export default function ChatPage() {
  const { chatId: urlChatId } = useParams<{ chatId: string }>()
  const {
    chats,
    activeChatId,
    getActiveChat,
    createChat,
    addMessage,
    setActiveChat,
  } = useChatStore()

  const [input, setInput] = useState('')
  const [expandedMessages, setExpandedMessages] = useState<Set<number>>(new Set())
  const scrollAreaRef = useRef<HTMLDivElement>(null)

  // Get active chat or create one if none exists
  const activeChat = getActiveChat()
  const messages = activeChat?.messages || []

  // Handle URL chat ID or create initial chat
  useEffect(() => {
    if (urlChatId) {
      // URL has a specific chat ID - activate it if it exists
      const chatExists = chats.some((c) => c.id === urlChatId)
      if (chatExists && activeChatId !== urlChatId) {
        setActiveChat(urlChatId)
      }
    } else if (chats.length === 0) {
      // No chats exist - create one
      createChat()
    } else if (!activeChatId && chats.length > 0) {
      // No active chat but chats exist - activate first one
      setActiveChat(chats[0].id)
    }
  }, [urlChatId, chats, activeChatId, createChat, setActiveChat])

  const scrollToBottom = () => {
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]')
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight
      }
    }
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const chatMutation = useMutation({
    mutationFn: (message: string) => {
      const history = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }))
      return sendChatMessage({ message, history })
    },
    onSuccess: (response: ChatResponse) => {
      if (activeChatId) {
        addMessage(activeChatId, {
          role: 'assistant',
          content: response.answer,
          sources: response.sources,
          graph_context: response.graph_context,
          vector_context: response.vector_context,
        })
      }
    },
    onError: (error) => {
      if (activeChatId) {
        addMessage(activeChatId, {
          role: 'assistant',
          content: `Fehler: ${error instanceof Error ? error.message : 'Unbekannter Fehler'}`,
        })
      }
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || chatMutation.isPending || !activeChatId) return

    const userMessage = input.trim()

    // Add user message to store
    addMessage(activeChatId, {
      role: 'user',
      content: userMessage,
    })

    setInput('')
    chatMutation.mutate(userMessage)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const toggleExpanded = (index: number) => {
    setExpandedMessages((prev) => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <header className="border-b border-border bg-card/50 px-6 py-4">
        <h1 className="text-xl font-semibold text-foreground">
          {activeChat?.name || 'Chat'}
        </h1>
        <p className="text-sm text-muted-foreground">
          Frage dein Wissen ab - basierend auf Vektoren und Graph
        </p>
      </header>

      {/* Messages */}
      <ScrollArea ref={scrollAreaRef} className="flex-1">
        <div className="space-y-6 p-6">
          {messages.length === 0 && (
            <div className="flex h-[60vh] flex-col items-center justify-center text-center">
              <Avatar className="mb-4 h-16 w-16 rounded-2xl">
                <AvatarFallback className="rounded-2xl bg-muted">
                  <Bot className="h-8 w-8 text-aurora-400" />
                </AvatarFallback>
              </Avatar>
              <h2 className="mb-2 text-xl font-semibold text-foreground">
                Willkommen bei Adizon Knowledge Core
              </h2>
              <p className="max-w-md text-muted-foreground">
                Stelle eine Frage zu deiner Wissensbasis. Ich durchsuche Dokumente
                und den Knowledge Graph, um dir die beste Antwort zu geben.
              </p>
            </div>
          )}

          {messages.map((message, index) => (
            <div
              key={message.id}
              className={cn(
                'flex gap-3',
                message.role === 'user' ? 'flex-row-reverse' : 'flex-row'
              )}
            >
              {/* Avatar */}
              <Avatar className="h-9 w-9 shrink-0 rounded-lg">
                <AvatarFallback
                  className={cn(
                    'rounded-lg',
                    message.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted'
                  )}
                >
                  {message.role === 'user' ? (
                    <User className="h-4 w-4" />
                  ) : (
                    <Bot className="h-4 w-4 text-aurora-400" />
                  )}
                </AvatarFallback>
              </Avatar>

              {/* Message Bubble */}
              <div
                className={cn(
                  'max-w-2xl rounded-2xl px-4 py-3',
                  message.role === 'user'
                    ? 'rounded-br-md bg-primary text-primary-foreground'
                    : 'rounded-bl-md border border-border bg-muted/50'
                )}
              >
                <p className="whitespace-pre-wrap text-sm">{message.content}</p>

                {/* Context Details for Assistant */}
                {message.role === 'assistant' &&
                  (message.sources?.length || message.graph_context) && (
                    <div className="mt-3 border-t border-border pt-3">
                      <button
                        onClick={() => toggleExpanded(index)}
                        className="flex items-center gap-2 text-xs text-muted-foreground transition-colors hover:text-foreground"
                      >
                        {expandedMessages.has(index) ? (
                          <ChevronUp className="h-3 w-3" />
                        ) : (
                          <ChevronDown className="h-3 w-3" />
                        )}
                        <span>Quellen & Kontext anzeigen</span>
                      </button>

                      {expandedMessages.has(index) && (
                        <div className="mt-3 space-y-3">
                          {/* Sources */}
                          {message.sources && message.sources.length > 0 && (
                            <div>
                              <div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
                                <FileText className="h-3 w-3" />
                                <span>Quellen</span>
                              </div>
                              <div className="flex flex-wrap gap-1.5">
                                {message.sources.map((source, i) => (
                                  <span
                                    key={i}
                                    className="rounded-md bg-background px-2 py-1 text-xs text-muted-foreground"
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
                                <div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
                                  <Network className="h-3 w-3" />
                                  <span>Graph-Kontext</span>
                                </div>
                                <pre className="overflow-x-auto rounded-lg bg-background p-3 text-xs text-muted-foreground">
                                  {message.graph_context}
                                </pre>
                              </div>
                            )}
                        </div>
                      )}
                    </div>
                  )}
              </div>
            </div>
          ))}

          {/* Loading State */}
          {chatMutation.isPending && (
            <div className="flex gap-3">
              <Avatar className="h-9 w-9 shrink-0 rounded-lg">
                <AvatarFallback className="rounded-lg bg-muted">
                  <Bot className="h-4 w-4 text-aurora-400" />
                </AvatarFallback>
              </Avatar>
              <div className="max-w-2xl space-y-2 rounded-2xl rounded-bl-md border border-border bg-muted/50 px-4 py-3">
                <Skeleton className="h-4 w-[280px]" />
                <Skeleton className="h-4 w-[200px]" />
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="border-t border-border bg-card/50 p-4">
        <form onSubmit={handleSubmit} className="mx-auto max-w-4xl">
          <div className="flex gap-3">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Stelle eine Frage... (Enter zum Senden, Shift+Enter für neue Zeile)"
              className="min-h-[44px] max-h-[120px] flex-1 resize-none"
              disabled={chatMutation.isPending}
              rows={1}
            />
            <Button
              type="submit"
              size="icon"
              disabled={!input.trim() || chatMutation.isPending}
              className="h-11 w-11 shrink-0"
            >
              <Send className="h-4 w-4" />
              <span className="sr-only">Senden</span>
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
