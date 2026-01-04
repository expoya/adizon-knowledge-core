# Adizon Knowledge Core - Architecture Documentation

## Overview

**Adizon Knowledge Core** ist ein Sovereign AI RAG-System (Retrieval-Augmented Generation) mit integrierter Knowledge Graph Funktionalität. Es kombiniert semantische Vektorsuche mit struktureller Graph-Abfrage für intelligente Dokumenten-Q&A mit Entity-Extraktion.

## Tech Stack

| Komponente | Technologie |
|------------|-------------|
| Backend | FastAPI + async Python 3.11 |
| Frontend | React 19 + TypeScript + Tailwind CSS |
| Vector Store | PostgreSQL + pgvector |
| Knowledge Graph | Neo4j 5.x |
| File Storage | MinIO (S3-kompatibel) |
| Embeddings | Jina German / OpenAI-kompatible APIs |
| LLM | Trooper/Ministral (self-hosted) |
| Workflow | LangGraph |

## Projektstruktur

```
adizon-knowledge-core/
├── backend/                    # FastAPI Backend (Port 8000)
│   ├── app/
│   │   ├── main.py            # Entry Point
│   │   ├── api/endpoints/     # REST Endpoints
│   │   ├── core/config.py     # Konfiguration
│   │   ├── db/                # Database Session
│   │   ├── models/            # SQLAlchemy Models
│   │   ├── services/          # Business Logic
│   │   ├── graph/             # Workflow Dispatcher
│   │   └── config/            # Ontology YAML
│   └── Dockerfile
├── frontend/                   # React Frontend (Port 5173/80)
│   ├── src/
│   │   ├── pages/             # Chat, Garden, Upload
│   │   ├── components/        # Reusable UI
│   │   └── api/client.ts      # API Client
│   └── Dockerfile
├── trooper_worker/             # Compute Worker (Port 8001)
│   ├── main.py                # Worker Entry
│   ├── workflow.py            # LangGraph Pipeline
│   ├── core/config.py         # Worker Config
│   ├── services/              # Processing Services
│   └── config/                # Ontology Files
├── deployment/                 # Deployment Configs
│   └── trooper/               # Trooper-spezifisch
├── docs/                       # Dokumentation
└── docker-compose.yml          # Local Stack
```

## Datenfluss

### 1. Document Upload

```
Frontend → POST /api/v1/upload → Backend
    ↓
SHA-256 Hash berechnen → Deduplizierung prüfen
    ↓
MinIO Upload → PostgreSQL Record (status=PENDING)
    ↓
HTTP POST → Trooper Worker /ingest
    ↓
Sofortige Response an Frontend
```

### 2. Document Processing (Trooper Worker)

```
Load (MinIO) → Split (Chunks) → Vector (PGVector) → Graph (Neo4j) → Finalize
    ↓              ↓                 ↓                  ↓              ↓
PDF/DOCX     3000 chars      Jina Embeddings    LLM Extraction   Callback
Sanitize     300 overlap     document_id        PENDING status   → Backend
```

### 3. Chat Query (Hybrid RAG)

```
Frontend → POST /api/v1/chat → Backend
    ↓
Vector Search (PGVector, k=5, threshold=0.8)
    +
Graph Search (Neo4j Cypher, APPROVED nodes)
    ↓
LLM (ChatOpenAI) mit kombiniertem Kontext
    ↓
Response mit Answer + Sources + Graph Context
```

## Microservices Architektur

```
┌─────────────┐     HTTP      ┌──────────────────┐
│   Frontend  │◄────────────► │     Backend      │
│  (React)    │               │    (FastAPI)     │
└─────────────┘               └────────┬─────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
            ┌───────────┐      ┌───────────┐      ┌───────────┐
            │ PostgreSQL│      │   Neo4j   │      │   MinIO   │
            │ (pgvector)│      │  (Graph)  │      │   (S3)    │
            └───────────┘      └───────────┘      └───────────┘
                    ▲                  ▲                  ▲
                    │                  │                  │
                    └──────────────────┼──────────────────┘
                                       │
                              ┌────────┴─────────┐
                              │  Trooper Worker  │
                              │   (LangGraph)    │
                              └──────────────────┘
```

## Datenbank Schemas

### PostgreSQL (knowledge_documents)

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary Key |
| filename | VARCHAR(512) | Original Filename |
| content_hash | VARCHAR(64) | SHA-256 (Unique, Dedupe) |
| file_size | BIGINT | Dateigröße |
| storage_path | TEXT | MinIO Pfad |
| status | ENUM | PENDING / INDEXED / ERROR |
| error_message | TEXT | Fehlermeldung |
| created_at | TIMESTAMP | Erstellungsdatum |

### Neo4j (Dynamic Labels)

**Node Labels** (aus Ontology): ORGANIZATION, PERSON, DEAL, PROJECT, PRODUCT, LOCATION

**Node Properties:**
- `name` (Merge Key)
- `status` (PENDING / APPROVED)
- `source_document_id`, `source_file`
- `created_at`, `updated_at`, `approved_at`

**Relationships:** WORKS_FOR, HAS_DEAL, INVOLVES_PRODUCT, LOCATED_AT, etc.

## API Endpoints

### Ingestion

| Method | Endpoint | Beschreibung |
|--------|----------|--------------|
| POST | `/api/v1/upload` | Dokument hochladen |
| GET | `/api/v1/documents` | Alle Dokumente auflisten |
| GET | `/api/v1/documents/{id}` | Einzelnes Dokument |
| POST | `/api/v1/documents/{id}/reprocess` | Erneut verarbeiten |
| POST | `/api/v1/documents/{id}/status` | Status-Update (Worker) |
| DELETE | `/api/v1/documents/{id}` | Löschen (kaskadierend) |

### Chat

| Method | Endpoint | Beschreibung |
|--------|----------|--------------|
| POST | `/api/v1/chat` | Hybrid RAG Chat |
| POST | `/api/v1/chat/stream` | Streaming Chat (SSE) |
| GET | `/api/v1/knowledge/summary` | Wissensbasis Übersicht |

### Graph

| Method | Endpoint | Beschreibung |
|--------|----------|--------------|
| GET | `/api/v1/graph/pending` | Ausstehende Nodes |
| POST | `/api/v1/graph/approve` | Nodes genehmigen |
| POST | `/api/v1/graph/reject` | Nodes ablehnen |
| POST | `/api/v1/graph/query` | Cypher Query ausführen |

## Multi-Tenant Ontology

Die Ontology wird via YAML konfiguriert (`ontology_voltage.yaml`):

```yaml
domain_name: "Voltage Solutions"
description: "B2B Photovoltaics provider"

node_types:
  - name: "ORGANIZATION"
    description: "Companies, Suppliers, Clients"
  # ...

relationship_types:
  - name: "WORKS_FOR"
    description: "Employment relationship"
  # ...
```

**SchemaFactory** generiert dynamisch Pydantic Models mit Literal-Constraints für typsichere LLM-Extraktion.

## Umgebungsvariablen

```bash
# PostgreSQL
POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD

# Neo4j
NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

# MinIO
MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET_NAME

# AI/LLM (Required)
EMBEDDING_API_URL, EMBEDDING_API_KEY, EMBEDDING_MODEL, LLM_MODEL_NAME

# Trooper Worker
TROOPER_URL, TROOPER_AUTH_TOKEN

# Ontology
ONTOLOGY_PATH
```

## Error Handling

1. **Document Processing Fehler:**
   - Status wird auf ERROR gesetzt
   - error_message enthält Details
   - Reprocess-Endpoint ermöglicht erneuten Versuch

2. **Graph Extraction Fehler:**
   - Non-fatal: Dokument wird trotzdem als INDEXED markiert
   - Nur Vektor-Fehler führen zu ERROR Status

3. **Worker Connectivity:**
   - 30s Timeout für Trooper-Requests
   - TrooperDispatchError bei Verbindungsproblemen
