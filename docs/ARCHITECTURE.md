# Adizon Knowledge Core - Architecture Documentation

## Overview

**Adizon Knowledge Core** ist ein Sovereign AI RAG-System (Retrieval-Augmented Generation) mit integrierter Knowledge Graph Funktionalität. Es kombiniert semantische Vektorsuche mit struktureller Graph-Abfrage für intelligente Dokumenten-Q&A mit Entity-Extraktion.

## System Architecture

```mermaid
graph TB
    subgraph Client["Client Layer"]
        FE[React Frontend<br/>Port 5173/80]
    end

    subgraph API["API Layer"]
        BE[FastAPI Backend<br/>Port 8000]
    end

    subgraph Worker["Processing Layer"]
        TW[Trooper Worker<br/>Port 8001<br/>LangGraph Pipeline]
    end

    subgraph Storage["Data Layer"]
        PG[(PostgreSQL<br/>+ pgvector)]
        NEO[(Neo4j<br/>Knowledge Graph)]
        MINIO[(MinIO<br/>S3 Storage)]
    end

    subgraph AI["AI Services"]
        EMB[Jina Embeddings<br/>German]
        LLM[Trooper/Ministral<br/>Self-hosted]
    end

    FE <-->|HTTP/REST| BE
    BE -->|POST /ingest| TW
    TW -->|Callback| BE

    BE --> PG
    BE --> NEO
    BE --> MINIO

    TW --> PG
    TW --> NEO
    TW --> MINIO
    TW --> EMB
    TW --> LLM

    BE --> EMB
    BE --> LLM
```

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

### Document Upload Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant BE as Backend
    participant MINIO as MinIO
    participant PG as PostgreSQL
    participant TW as Trooper Worker

    FE->>BE: POST /api/v1/upload
    BE->>BE: SHA-256 Hash berechnen
    BE->>PG: Deduplizierung prüfen
    alt Duplicate
        PG-->>BE: Existing document
        BE-->>FE: 409 Conflict
    else New Document
        BE->>MINIO: Upload File
        BE->>PG: INSERT (status=PENDING)
        BE->>TW: POST /ingest
        TW-->>BE: 202 Accepted
        BE-->>FE: 201 Created
    end
```

### Document Processing Pipeline

```mermaid
graph LR
    subgraph TW["Trooper Worker - LangGraph"]
        LOAD[Load<br/>MinIO] --> SPLIT[Split<br/>Chunks]
        SPLIT --> VECTOR[Vector<br/>PGVector]
        VECTOR --> GRAPH[Graph<br/>Neo4j]
        GRAPH --> FINAL[Finalize<br/>Callback]
    end

    LOAD -.->|PDF/DOCX<br/>Sanitize| SPLIT
    SPLIT -.->|3000 chars<br/>300 overlap| VECTOR
    VECTOR -.->|Jina Embeddings<br/>document_id| GRAPH
    GRAPH -.->|LLM Extraction<br/>PENDING status| FINAL
    FINAL -.->|HTTP Callback| BE[Backend]
```

### Chat Query Flow (Hybrid RAG)

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant BE as Backend
    participant PG as PostgreSQL<br/>+ pgvector
    participant NEO as Neo4j
    participant LLM as LLM

    FE->>BE: POST /api/v1/chat

    par Vector Search
        BE->>PG: Similarity Search<br/>k=5, threshold=0.8
        PG-->>BE: Relevant Chunks
    and Graph Search
        BE->>NEO: Cypher Query<br/>APPROVED nodes
        NEO-->>BE: Graph Context
    end

    BE->>BE: Merge Context
    BE->>LLM: Generate Response
    LLM-->>BE: Answer
    BE-->>FE: Response + Sources + Graph
```

## Microservices Architecture

```mermaid
graph TB
    subgraph External["External Access"]
        USER((User))
    end

    subgraph Frontend["Frontend Container"]
        REACT[React App<br/>Nginx]
    end

    subgraph Backend["Backend Container"]
        FASTAPI[FastAPI<br/>Async Python]
    end

    subgraph Worker["Worker Container"]
        LANGGRAPH[LangGraph<br/>Pipeline]
    end

    subgraph Databases["Database Containers"]
        POSTGRES[(PostgreSQL<br/>pgvector)]
        NEO4J[(Neo4j<br/>Graph DB)]
        MINIO[(MinIO<br/>Object Store)]
    end

    USER --> REACT
    REACT <--> FASTAPI
    FASTAPI --> LANGGRAPH
    LANGGRAPH --> FASTAPI

    FASTAPI --> POSTGRES
    FASTAPI --> NEO4J
    FASTAPI --> MINIO

    LANGGRAPH --> POSTGRES
    LANGGRAPH --> NEO4J
    LANGGRAPH --> MINIO
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

### Neo4j Schema

```mermaid
graph LR
    subgraph Nodes["Node Labels (Ontology)"]
        ORG[ORGANIZATION]
        PER[PERSON]
        DEAL[DEAL]
        PROJ[PROJECT]
        PROD[PRODUCT]
        LOC[LOCATION]
    end

    PER -->|WORKS_FOR| ORG
    ORG -->|HAS_DEAL| DEAL
    DEAL -->|INVOLVES_PRODUCT| PROD
    ORG -->|LOCATED_AT| LOC
    PER -->|CONTACT_FOR| DEAL
    PROD -->|PART_OF_PROJECT| PROJ
    ORG -->|SUPPLIES| ORG
    PER -->|MANAGES| PROJ
```

**Node Properties:**
- `name` (Merge Key)
- `status` (PENDING / APPROVED)
- `source_document_id`, `source_file`
- `created_at`, `updated_at`, `approved_at`

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

```mermaid
flowchart TD
    START[Document Processing] --> LOAD{Load OK?}
    LOAD -->|Yes| SPLIT{Split OK?}
    LOAD -->|No| ERR1[Status: ERROR<br/>error_message set]

    SPLIT -->|Yes| VEC{Vector OK?}
    SPLIT -->|No| ERR2[Status: ERROR]

    VEC -->|Yes| GRAPH{Graph OK?}
    VEC -->|No| ERR3[Status: ERROR]

    GRAPH -->|Yes| SUCCESS[Status: INDEXED]
    GRAPH -->|No| PARTIAL[Status: INDEXED<br/>Graph skipped<br/>non-fatal]

    ERR1 --> RETRY[Reprocess Endpoint<br/>available]
    ERR2 --> RETRY
    ERR3 --> RETRY
```

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
