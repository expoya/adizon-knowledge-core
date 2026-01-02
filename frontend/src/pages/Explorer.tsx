import { useState, useEffect } from 'react'

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

const STATUS_CONFIG = {
  pending: {
    label: 'Pending',
    bgColor: 'bg-gray-500/10',
    textColor: 'text-gray-400',
    dotColor: 'bg-gray-400',
  },
  processing: {
    label: 'Processing',
    bgColor: 'bg-amber-500/10',
    textColor: 'text-amber-400',
    dotColor: 'bg-amber-400 animate-pulse',
  },
  indexed: {
    label: 'Indexed',
    bgColor: 'bg-emerald-500/10',
    textColor: 'text-emerald-400',
    dotColor: 'bg-emerald-400',
  },
  failed: {
    label: 'Failed',
    bgColor: 'bg-red-500/10',
    textColor: 'text-red-400',
    dotColor: 'bg-red-400',
  },
}

export default function Explorer() {
  const [documents, setDocuments] = useState<Document[]>(DUMMY_DOCUMENTS)
  const [isLoading, setIsLoading] = useState(false)

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

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-white">Knowledge Explorer</h2>
          <p className="mt-1 text-gray-400">
            Browse and manage your indexed documents
          </p>
        </div>
        
        {/* Stats */}
        <div className="flex gap-4">
          <div className="px-4 py-2 bg-midnight-900 rounded-lg">
            <div className="text-2xl font-semibold text-white">{documents.length}</div>
            <div className="text-xs text-gray-500">Documents</div>
          </div>
          <div className="px-4 py-2 bg-midnight-900 rounded-lg">
            <div className="text-2xl font-semibold text-emerald-400">
              {documents.filter(d => d.status === 'indexed').length}
            </div>
            <div className="text-xs text-gray-500">Indexed</div>
          </div>
        </div>
      </div>

      {/* Documents Table */}
      <div className="bg-midnight-900/50 rounded-xl border border-midnight-800 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-midnight-800">
              <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Document
              </th>
              <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Uploaded
              </th>
              <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Hash
              </th>
              <th className="px-6 py-4 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-midnight-800">
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                  <svg className="w-8 h-8 animate-spin mx-auto mb-2" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Loading documents...
                </td>
              </tr>
            ) : documents.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                  No documents yet. Upload some files to get started.
                </td>
              </tr>
            ) : (
              documents.map((doc) => {
                const statusConfig = STATUS_CONFIG[doc.status]
                return (
                  <tr key={doc.id} className="hover:bg-midnight-800/50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-midnight-800 flex items-center justify-center">
                          <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        </div>
                        <div>
                          <div className="font-medium text-white">{doc.filename}</div>
                          <div className="text-xs text-gray-500">ID: {doc.id}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${statusConfig.bgColor} ${statusConfig.textColor}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${statusConfig.dotColor}`} />
                        {statusConfig.label}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-400">
                      {formatDate(doc.created_at)}
                    </td>
                    <td className="px-6 py-4">
                      <code className="text-xs text-gray-500 font-mono bg-midnight-800 px-2 py-1 rounded">
                        {doc.content_hash.slice(0, 12)}...
                      </code>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button className="text-gray-400 hover:text-white transition-colors p-2 rounded-lg hover:bg-midnight-800">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
                        </svg>
                      </button>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

