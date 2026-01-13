/**
 * Zustand Store for Chat State Management
 * Persists to localStorage for offline access
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { Chat, ChatMessage } from '@/types/chat'

interface ChatState {
  chats: Chat[]
  activeChatId: string | null

  // Getters
  getActiveChat: () => Chat | undefined

  // Actions
  createChat: () => string
  deleteChat: (chatId: string) => void
  renameChat: (chatId: string, name: string) => void
  setActiveChat: (chatId: string | null) => void
  addMessage: (chatId: string, message: Omit<ChatMessage, 'id' | 'timestamp'>) => void
  clearMessages: (chatId: string) => void
}

// Generate unique ID
const generateId = () => `chat_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
const generateMessageId = () => `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`

// Truncate text for chat name
const truncateForName = (text: string, maxLength: number = 40): string => {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength).trim() + '...'
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      chats: [],
      activeChatId: null,

      getActiveChat: () => {
        const { chats, activeChatId } = get()
        return chats.find((chat) => chat.id === activeChatId)
      },

      createChat: () => {
        const newChat: Chat = {
          id: generateId(),
          name: 'Neuer Chat',
          messages: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
        }

        set((state) => ({
          chats: [newChat, ...state.chats],
          activeChatId: newChat.id,
        }))

        return newChat.id
      },

      deleteChat: (chatId: string) => {
        set((state) => {
          const newChats = state.chats.filter((chat) => chat.id !== chatId)
          const newActiveId =
            state.activeChatId === chatId
              ? newChats.length > 0
                ? newChats[0].id
                : null
              : state.activeChatId

          return {
            chats: newChats,
            activeChatId: newActiveId,
          }
        })
      },

      renameChat: (chatId: string, name: string) => {
        set((state) => ({
          chats: state.chats.map((chat) =>
            chat.id === chatId
              ? { ...chat, name, updatedAt: Date.now() }
              : chat
          ),
        }))
      },

      setActiveChat: (chatId: string | null) => {
        set({ activeChatId: chatId })
      },

      addMessage: (chatId: string, message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
        const newMessage: ChatMessage = {
          ...message,
          id: generateMessageId(),
          timestamp: Date.now(),
        }

        set((state) => ({
          chats: state.chats.map((chat) => {
            if (chat.id !== chatId) return chat

            const updatedChat = {
              ...chat,
              messages: [...chat.messages, newMessage],
              updatedAt: Date.now(),
            }

            // Auto-name chat after first user message
            if (
              chat.name === 'Neuer Chat' &&
              message.role === 'user' &&
              chat.messages.length === 0
            ) {
              updatedChat.name = truncateForName(message.content)
            }

            return updatedChat
          }),
        }))
      },

      clearMessages: (chatId: string) => {
        set((state) => ({
          chats: state.chats.map((chat) =>
            chat.id === chatId
              ? { ...chat, messages: [], updatedAt: Date.now() }
              : chat
          ),
        }))
      },
    }),
    {
      name: 'adizon-chat-storage',
      version: 1,
    }
  )
)
