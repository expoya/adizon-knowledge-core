import { useState, useEffect, useMemo } from 'react'
import {
  Search,
  FileText,
  MoreHorizontal,
  Eye,
  Trash2,
  RefreshCw,
  Loader2,
  FolderOpen,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Card, CardContent } from '@/components/ui/card'

interface Document {
  id: string
  filename: string
  status: 'pending' | 'processing' | 'indexed' | 'failed'
  created_at: string
  content_hash: string
}

// Dummy data for initial development
const DUMMY_DOCUMENTS: Document[] = [
  {
    id: '1',
    filename: 'company-handbook.pdf',
    status: 'indexed',
    created_at: '2026-01-02T10:30:00Z',
    content_hash: 'abc123def456',
  },
  {
    id: '2',
    filename: 'product-roadmap-2026.docx',
    status: 'processing',
    created_at: '2026-01-02T09:15:00Z',
    content_hash: 'xyz789ghi012',
  },
  {
    id: '3',
    filename: 'technical-architecture.md',
    status: 'pending',
    created_at: '2026-01-02T08:45:00Z',
    content_hash: 'mno345pqr678',
  },
  {
    id: '4',
    filename: 'api-documentation.pdf',
    status: 'failed',
    created_at: '2026-01-01T16:20:00Z',
    content_hash: 'stu901vwx234',
  },
]

const STATUS_OPTIONS = [
  { value: 'all', label: 'Alle Status' },
  { value: 'indexed', label: 'Indexiert' },
  { value: 'processing', label: 'Verarbeitung' },
  { value: 'pending', label: 'Wartend' },
  { value: 'failed', label: 'Fehlgeschlagen' },
]

function getStatusBadge(status: Document['status']) {
  switch (status) {
    case 'indexed':
      return (
        <Badge variant="default" className="bg-green-500/20 text-green-400 border-green-500/30">
          <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-green-400" />
          Indexiert
        </Badge>
      )
    case 'processing':
      return (
        <Badge variant="secondary" className="bg-amber-500/20 text-amber-400 border-amber-500/30">
          <span className="mr-1.5 h-1.5 w-1.5 animate-pulse rounded-full bg-amber-400" />
          Verarbeitung
        </Badge>
      )
    case 'pending':
      return (
        <Badge variant="outline" className="text-muted-foreground">
          <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-muted-foreground" />
          Wartend
        </Badge>
      )
    case 'failed':
      return (
        <Badge variant="destructive" className="bg-red-500/20 text-red-400 border-red-500/30">
          <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-red-400" />
          Fehlgeschlagen
        </Badge>
      )
  }
}

function getFileTypeBadge(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase()
  switch (ext) {
    case 'pdf':
      return <Badge variant="outline" className="text-xs">PDF</Badge>
    case 'docx':
    case 'doc':
      return <Badge variant="outline" className="text-xs">DOCX</Badge>
    case 'md':
      return <Badge variant="outline" className="text-xs">MD</Badge>
    case 'txt':
      return <Badge variant="outline" className="text-xs">TXT</Badge>
    default:
      return <Badge variant="outline" className="text-xs">{ext?.toUpperCase()}</Badge>
  }
}

export default function Explorer() {
  const [documents, setDocuments] = useState<Document[]>(DUMMY_DOCUMENTS)
  const [isLoading, setIsLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  // Fetch documents from API (using dummy data for now)
  useEffect(() => {
    const fetchDocuments = async () => {
      setIsLoading(true)
      try {
        const response = await fetch('/api/documents')
        if (response.ok) {
          const data = await response.json()
          setDocuments(data.items || DUMMY_DOCUMENTS)
        }
      } catch {
        // Use dummy data on error
        setDocuments(DUMMY_DOCUMENTS)
      } finally {
        setIsLoading(false)
      }
    }

    fetchDocuments()
  }, [])

  const filteredDocuments = useMemo(() => {
    return documents.filter((doc) => {
      const matchesSearch = doc.filename.toLowerCase().includes(searchQuery.toLowerCase())
      const matchesStatus = statusFilter === 'all' || doc.status === statusFilter
      return matchesSearch && matchesStatus
    })
  }, [documents, searchQuery, statusFilter])

  const stats = useMemo(() => ({
    total: documents.length,
    indexed: documents.filter(d => d.status === 'indexed').length,
  }), [documents])

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const handleRefresh = () => {
    setIsLoading(true)
    setTimeout(() => {
      setDocuments(DUMMY_DOCUMENTS)
      setIsLoading(false)
    }, 500)
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <header className="border-b border-border bg-card/50 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-foreground">Knowledge Explorer</h1>
            <p className="text-sm text-muted-foreground">
              Durchsuche und verwalte deine indexierten Dokumente
            </p>
          </div>

          {/* Stats */}
          <div className="flex gap-3">
            <Card className="border-border bg-card">
              <CardContent className="px-4 py-2">
                <div className="text-2xl font-semibold text-foreground">{stats.total}</div>
                <div className="text-xs text-muted-foreground">Dokumente</div>
              </CardContent>
            </Card>
            <Card className="border-border bg-card">
              <CardContent className="px-4 py-2">
                <div className="text-2xl font-semibold text-green-400">{stats.indexed}</div>
                <div className="text-xs text-muted-foreground">Indexiert</div>
              </CardContent>
            </Card>
          </div>
        </div>
      </header>

      {/* Toolbar */}
      <div className="border-b border-border bg-card/30 px-6 py-3">
        <div className="flex items-center gap-3">
          {/* Search */}
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Dokumente suchen..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* Status Filter */}
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="Status filtern" />
            </SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Refresh Button */}
          <Button variant="outline" size="icon" onClick={handleRefresh} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Dokument</TableHead>
                <TableHead>Typ</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Hochgeladen</TableHead>
                <TableHead>Hash</TableHead>
                <TableHead className="w-[50px]"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-32 text-center">
                    <div className="flex flex-col items-center justify-center text-muted-foreground">
                      <Loader2 className="mb-2 h-8 w-8 animate-spin" />
                      <span>Lade Dokumente...</span>
                    </div>
                  </TableCell>
                </TableRow>
              ) : filteredDocuments.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-32 text-center">
                    <div className="flex flex-col items-center justify-center text-muted-foreground">
                      <FolderOpen className="mb-2 h-8 w-8" />
                      <span>
                        {searchQuery || statusFilter !== 'all'
                          ? 'Keine Dokumente gefunden'
                          : 'Noch keine Dokumente vorhanden'}
                      </span>
                      {!searchQuery && statusFilter === 'all' && (
                        <span className="mt-1 text-xs">
                          Lade Dateien hoch, um zu beginnen
                        </span>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                filteredDocuments.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted">
                          <FileText className="h-4 w-4 text-muted-foreground" />
                        </div>
                        <div>
                          <div className="font-medium">{doc.filename}</div>
                          <div className="text-xs text-muted-foreground">ID: {doc.id}</div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      {getFileTypeBadge(doc.filename)}
                    </TableCell>
                    <TableCell>
                      {getStatusBadge(doc.status)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(doc.created_at)}
                    </TableCell>
                    <TableCell>
                      <code className="rounded bg-muted px-2 py-1 font-mono text-xs text-muted-foreground">
                        {doc.content_hash.slice(0, 8)}...
                      </code>
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreHorizontal className="h-4 w-4" />
                            <span className="sr-only">Aktionen</span>
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem>
                            <Eye className="mr-2 h-4 w-4" />
                            Details anzeigen
                          </DropdownMenuItem>
                          <DropdownMenuItem>
                            <RefreshCw className="mr-2 h-4 w-4" />
                            Neu indexieren
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem className="text-destructive focus:text-destructive">
                            <Trash2 className="mr-2 h-4 w-4" />
                            Löschen
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </Card>
      </div>
    </div>
  )
}
