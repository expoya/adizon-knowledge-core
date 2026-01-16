import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  MessageSquare,
  Upload,
  Database,
  Sparkles,
  Globe,
  Menu,
  Plus,
  Trash2,
  X,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Toaster } from '@/components/ui/sonner'
import { cn } from '@/lib/utils'
import { useChatStore } from '@/stores/chatStore'

const navItems = [
  { to: '/', icon: MessageSquare, label: 'Chat', end: true },
  { to: '/upload', icon: Upload, label: 'Upload', end: false },
  { to: '/explorer', icon: Globe, label: 'Explorer', end: false },
]

function NavItem({
  to,
  icon: Icon,
  label,
  end = false,
  onClick,
}: {
  to: string
  icon: React.ElementType
  label: string
  end?: boolean
  onClick?: () => void
}) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
          isActive
            ? 'bg-accent text-accent-foreground'
            : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'
        )
      }
    >
      <Icon className="h-4 w-4" />
      {label}
    </NavLink>
  )
}

function SidebarContent({ onNavClick }: { onNavClick?: () => void }) {
  const location = useLocation()
  const { chats, activeChatId, createChat, deleteChat, setActiveChat } = useChatStore()
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)

  const isChatRoute = location.pathname === '/' || location.pathname.startsWith('/chat')

  const handleNewChat = () => {
    createChat()
    onNavClick?.()
  }

  const handleSelectChat = (chatId: string) => {
    setActiveChat(chatId)
    setDeleteConfirmId(null)
    onNavClick?.()
  }

  const handleDeleteClick = (e: React.MouseEvent, chatId: string) => {
    e.stopPropagation()
    setDeleteConfirmId(chatId)
  }

  const handleConfirmDelete = (e: React.MouseEvent, chatId: string) => {
    e.stopPropagation()
    deleteChat(chatId)
    setDeleteConfirmId(null)
  }

  const handleCancelDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    setDeleteConfirmId(null)
  }

  return (
    <div className="flex h-full flex-col">
      {/* Logo */}
      <div className="flex items-center gap-3 px-3 py-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-aurora-400 to-primary">
          <Database className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="font-semibold text-foreground">Adizon</h1>
          <p className="text-xs text-muted-foreground">Knowledge Core</p>
        </div>
      </div>

      {/* New Chat Button */}
      <div className="px-2 py-3">
        <Button
          onClick={handleNewChat}
          variant="outline"
          className="w-full justify-start gap-2"
        >
          <Plus className="h-4 w-4" />
          <span>Neuer Chat</span>
        </Button>
      </div>

      {/* Chat List */}
      <ScrollArea className="flex-1 px-2">
        <div className="space-y-1">
          {chats.length === 0 ? (
            <p className="px-3 py-4 text-center text-xs text-muted-foreground">
              Noch keine Chats
            </p>
          ) : (
            chats.map((chat) => (
              <div
                key={chat.id}
                onClick={() => handleSelectChat(chat.id)}
                className={cn(
                  'group relative flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 transition-colors',
                  isChatRoute && activeChatId === chat.id
                    ? 'bg-accent text-accent-foreground'
                    : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
                )}
              >
                <MessageSquare className="h-4 w-4 shrink-0" />

                <span className="min-w-0 flex-1 truncate text-sm">{chat.name}</span>

                {/* Delete Button / Confirm */}
                {deleteConfirmId === chat.id ? (
                  <div className="flex shrink-0 items-center gap-1">
                    <Button
                      size="icon"
                      variant="destructive"
                      className="h-6 w-6"
                      onClick={(e) => handleConfirmDelete(e, chat.id)}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-6 w-6"
                      onClick={handleCancelDelete}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                ) : (
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-6 w-6 shrink-0 text-muted-foreground/50 hover:text-destructive"
                    onClick={(e) => handleDeleteClick(e, chat.id)}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                )}
              </div>
            ))
          )}
        </div>
      </ScrollArea>

      <Separator className="my-2" />

      {/* Bottom Navigation - Upload & Explorer */}
      <nav className="space-y-1 px-2 pb-2">
        {navItems.map((item) => (
          <NavItem key={item.to} {...item} onClick={onNavClick} />
        ))}
      </nav>

      {/* Footer */}
      <div className="flex items-center gap-2 border-t border-border px-3 py-3 text-xs text-muted-foreground">
        <Sparkles className="h-3 w-3" />
        <span>Sovereign AI RAG</span>
      </div>
    </div>
  )
}

export default function Layout() {
  const [sheetOpen, setSheetOpen] = useState(false)

  return (
    <div className="flex h-screen bg-background">
      {/* Desktop Sidebar */}
      <aside className="hidden w-64 flex-col border-r border-border bg-card/50 p-2 md:flex">
        <SidebarContent />
      </aside>

      {/* Mobile Header + Sheet */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-14 items-center gap-4 border-b border-border bg-card/50 px-4 md:hidden">
          <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="shrink-0">
                <Menu className="h-5 w-5" />
                <span className="sr-only">Toggle navigation menu</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="flex w-64 flex-col p-2">
              <SheetHeader className="sr-only">
                <SheetTitle>Navigation</SheetTitle>
              </SheetHeader>
              <SidebarContent onNavClick={() => setSheetOpen(false)} />
            </SheetContent>
          </Sheet>

          {/* Mobile Logo */}
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-aurora-400 to-primary">
              <Database className="h-4 w-4 text-white" />
            </div>
            <span className="font-semibold text-foreground">Adizon</span>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>

      {/* Global Toaster */}
      <Toaster position="bottom-right" />
    </div>
  )
}
