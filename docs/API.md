# API Reference

Base URL: `http://localhost:8000/api/v1`

---

## Document Ingestion

### Upload Document

```http
POST /upload
Content-Type: multipart/form-data
```

**Request:**
```
file: <binary>
```

**Response (201):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "vertrag.pdf",
  "content_hash": "sha256...",
  "file_size": 245678,
  "storage_path": "raw/2025/01/abc123_vertrag.pdf",
  "status": "PENDING",
  "created_at": "2025-01-04T10:30:00Z",
  "is_duplicate": false,
  "message": "Document uploaded. Processing started in background."
}
```

**Deduplizierung:** Bei identischem `content_hash` wird `is_duplicate: true` zurückgegeben.

---

### List Documents

```http
GET /documents?status=INDEXED&limit=100&offset=0
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| status | string | - | Filter: PENDING, INDEXED, ERROR |
| limit | int | 100 | Max Ergebnisse |
| offset | int | 0 | Pagination Offset |

**Response (200):**
```json
[
  {
    "id": "...",
    "filename": "vertrag.pdf",
    "status": "INDEXED",
    "created_at": "..."
  }
]
```

---

### Get Document

```http
GET /documents/{document_id}
```

**Response (200):**
```json
{
  "id": "...",
  "filename": "vertrag.pdf",
  "content_hash": "...",
  "file_size": 245678,
  "storage_path": "...",
  "status": "INDEXED",
  "created_at": "...",
  "message": null
}
```

**Response (404):** Document not found

---

### Reprocess Document

```http
POST /documents/{document_id}/reprocess
```

Setzt Status auf PENDING und triggert erneute Verarbeitung.

**Response (200):**
```json
{
  "id": "...",
  "status": "PENDING",
  "message": "Reprocessing started in background."
}
```

---

### Update Document Status (Worker Callback)

```http
POST /documents/{document_id}/status
Content-Type: application/json
```

**Request:**
```json
{
  "status": "INDEXED",
  "error_message": null
}
```

**Status Values:** `PENDING`, `INDEXED`, `ERROR`

**Response (200):**
```json
{
  "document_id": "...",
  "status": "INDEXED",
  "message": "Document status updated to INDEXED"
}
```

---

### Delete Document

```http
DELETE /documents/{document_id}
```

Löscht kaskadierend:
1. Vektoren aus PGVector
2. Graph-Nodes aus Neo4j
3. Datei aus MinIO
4. Metadaten aus PostgreSQL

**Response (200):**
```json
{
  "id": "...",
  "filename": "vertrag.pdf",
  "vectors_deleted": true,
  "graph_nodes_deleted": 5,
  "storage_deleted": true,
  "message": "Document 'vertrag.pdf' and associated data deleted successfully."
}
```

---

## Chat

### Send Message

```http
POST /chat
Content-Type: application/json
```

**Request:**
```json
{
  "message": "Wer ist der Ansprechpartner für Projekt Solar München?",
  "conversation_history": [
    {"role": "user", "content": "Vorherige Frage"},
    {"role": "assistant", "content": "Vorherige Antwort"}
  ]
}
```

**Response (200):**
```json
{
  "answer": "Der Ansprechpartner für Projekt Solar München ist Max Mustermann von der Firma XYZ GmbH.",
  "sources": [
    {
      "filename": "projekt_solar.pdf",
      "chunk_index": 2,
      "relevance_score": 0.85
    }
  ],
  "graph_context": "- PERSON 'Max Mustermann' WORKS_FOR 'XYZ GmbH'\n- PROJECT 'Solar München' ...",
  "vector_context": "Relevante Textpassagen..."
}
```

---

### Streaming Chat

```http
POST /chat/stream
Content-Type: application/json
```

**Request:** Identisch zu `/chat`

**Response:** Server-Sent Events (SSE)

```
data: {"token": "Der"}
data: {"token": " Ansprech"}
data: {"token": "partner"}
...
data: {"done": true}
```

---

### Knowledge Summary

```http
GET /knowledge/summary
```

**Response (200):**
```json
{
  "summary": "Knowledge Graph (APPROVED):\n  - 45 ORGANIZATION\n  - 128 PERSON\n  - 23 PROJECT\n\n⏳ 12 Entitäten warten auf Review (PENDING)"
}
```

---

## Graph Management

### Get Pending Nodes

```http
GET /graph/pending
```

**Response (200):**
```json
[
  {
    "element_id": "4:abc123:0",
    "labels": ["PERSON"],
    "name": "Max Mustermann",
    "properties": {
      "source_file": "vertrag.pdf",
      "created_at": "2025-01-04T10:30:00Z"
    }
  }
]
```

---

### Approve Nodes

```http
POST /graph/approve
Content-Type: application/json
```

**Request:**
```json
{
  "node_ids": ["4:abc123:0", "4:def456:1"]
}
```

**Response (200):**
```json
{
  "approved_count": 2,
  "message": "2 nodes approved"
}
```

---

### Reject Nodes

```http
POST /graph/reject
Content-Type: application/json
```

**Request:**
```json
{
  "node_ids": ["4:xyz789:2"]
}
```

**Response (200):**
```json
{
  "rejected_count": 1,
  "message": "1 nodes rejected and deleted"
}
```

---

### Execute Cypher Query

```http
POST /graph/query
Content-Type: application/json
```

**Request:**
```json
{
  "query": "MATCH (n:PERSON) RETURN n.name LIMIT 10",
  "parameters": {}
}
```

**Response (200):**
```json
{
  "results": [
    {"n.name": "Max Mustermann"},
    {"n.name": "Anna Schmidt"}
  ]
}
```

**Warnung:** Erlaubt beliebige Cypher-Befehle inkl. DELETE.

---

## Trooper Worker API

Base URL: `http://localhost:8001`

### Health Check

```http
GET /health
```

**Response (200):**
```json
{
  "status": "healthy",
  "service": "trooper-worker"
}
```

---

### Ingest Document

```http
POST /ingest
Content-Type: application/json
Authorization: Bearer <token>  # Optional
```

**Request:**
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "vertrag.pdf",
  "storage_path": "raw/2025/01/abc123_vertrag.pdf"
}
```

**Response (200):**
```json
{
  "status": "accepted",
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Task accepted for background processing: vertrag.pdf"
}
```

Verarbeitung erfolgt asynchron. Nach Abschluss ruft Worker `POST /documents/{id}/status` am Backend auf.

---

## Error Responses

### 400 Bad Request

```json
{
  "detail": "Invalid document ID format"
}
```

### 404 Not Found

```json
{
  "detail": "Document with ID xyz not found"
}
```

### 500 Internal Server Error

```json
{
  "detail": "Failed to upload to storage: Connection refused"
}
```
