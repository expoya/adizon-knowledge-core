import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  MessageSquare,
  Upload,
  Database,
  Sparkles,
  Globe,
  Menu,
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
import { Toaster } from '@/components/ui/sonner'
import { cn } from '@/lib/utils'

const navItems = [
  { to: '/explorer', icon: Globe, label: 'Explorer' },
  { to: '/', icon: MessageSquare, label: 'Chat' },
  { to: '/upload', icon: Upload, label: 'Upload' },
]

function NavItem({ to, icon: Icon, label, onClick }: {
  to: string
  icon: React.ElementType
  label: string
  onClick?: () => void
}) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
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
  return (
    <>
      {/* Logo */}
      <div className="flex items-center gap-3 px-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-aurora-400 to-primary">
          <Database className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="font-semibold text-foreground">Adizon</h1>
          <p className="text-xs text-muted-foreground">Knowledge Core</p>
        </div>
      </div>

      <Separator className="my-4" />

      {/* Navigation */}
      <nav className="flex-1 space-y-1">
        {navItems.map((item) => (
          <NavItem key={item.to} {...item} onClick={onNavClick} />
        ))}
      </nav>

      <Separator className="my-4" />

      {/* Footer */}
      <div className="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground">
        <Sparkles className="h-3 w-3" />
        <span>Sovereign AI RAG</span>
      </div>
    </>
  )
}

export default function Layout() {
  const [sheetOpen, setSheetOpen] = useState(false)

  return (
    <div className="flex h-screen bg-background">
      {/* Desktop Sidebar */}
      <aside className="hidden w-56 flex-col border-r border-border bg-card/50 p-4 md:flex">
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
            <SheetContent side="left" className="flex w-56 flex-col p-4">
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
