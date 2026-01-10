# Adizon Knowledge Core - Architecture Documentation

## Overview

**Adizon Knowledge Core** (auch bekannt als **Adizon Enterprise-Intelligence-System**) ist ein fortschrittliches, agentisches RAG-System (Retrieval-Augmented Generation) mit integrierter Knowledge Graph Funktionalität und SQL-Integrationsfähigkeiten. Es kombiniert drei Hauptdatenquellen:

1. **Semantische Vektorsuche** (pgvector) für Dokumenten-Chunks
2. **Knowledge Graph** (Neo4j) für Entity-Beziehungen
3. **Externe SQL-Datenbanken** für strukturierte Geschäftsdaten

Das System nutzt **LangGraph** für intelligentes, autonomes Routing und Multi-Source Intelligence.

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
│   │   │   ├── chat.py        # ⭐ Agentic RAG Integration
│   │   │   ├── ingestion.py
│   │   │   └── graph.py
│   │   ├── core/
│   │   │   ├── config.py      # Konfiguration
│   │   │   └── llm.py         # ⭐ LLM Factory
│   │   ├── db/                # Database Session
│   │   ├── models/            # SQLAlchemy Models
│   │   ├── services/          # Business Logic
│   │   │   ├── metadata_store.py    # ⭐ External Sources
│   │   │   ├── sql_connector.py     # ⭐ SQL Connections
│   │   │   ├── vector_store.py
│   │   │   ├── graph_store.py
│   │   │   └── storage.py
│   │   ├── graph/             # LangGraph Workflows
│   │   │   ├── chat_workflow.py     # ⭐ Agentic RAG
│   │   │   └── ingestion_workflow.py
│   │   ├── tools/             # ⭐ Agent Tools
│   │   │   ├── knowledge.py   # Knowledge Search
│   │   │   └── sql.py         # SQL Execution
│   │   └── config/            # Configuration Files
│   │       ├── ontology_voltage.yaml
│   │       └── external_sources.yaml  # ⭐ SQL Sources
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

### Chat Query Flow (Agentic RAG v2.0)

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant BE as Backend API
    participant WF as LangGraph Workflow
    participant ROUTER as Router Node
    participant SQL as SQL Node
    participant KB as Knowledge Node
    participant CRM as CRM Node
    participant GEN as Generator Node
    participant EXDB as External DB
    participant PG as PostgreSQL<br/>+ pgvector
    participant NEO as Neo4j
    participant ZOHO as Zoho CRM

    FE->>BE: POST /api/v1/chat
    BE->>WF: Execute Workflow
    
    WF->>ROUTER: Classify Intent
    ROUTER->>ROUTER: LLM Analysis
    
    alt SQL Intent
        ROUTER->>SQL: Route to SQL
        SQL->>SQL: Get Schema
        SQL->>SQL: Generate Query
        SQL->>EXDB: Execute SQL
        EXDB-->>SQL: Results
        SQL->>GEN: SQL Context
    else Knowledge/CRM Intent
        ROUTER->>NEO: Search for CRM entities
        NEO-->>ROUTER: Entity with source_id (optional)
        ROUTER->>KB: Route to Knowledge
        par Hybrid Search
            KB->>PG: Vector Search
            PG-->>KB: Chunks
        and
            KB->>NEO: Graph Query
            NEO-->>KB: Entities
        end
        KB->>KB: Store Knowledge Context
        
        alt CRM Target Found
            KB->>CRM: Route to CRM Node
            CRM->>ZOHO: get_crm_facts(entity_id)
            ZOHO-->>CRM: Live CRM Data
            CRM->>GEN: CRM + Knowledge Context
        else No CRM Target
            KB->>GEN: Knowledge Context Only
        end
    end
    
    GEN->>GEN: Synthesize Answer
    GEN-->>WF: Final Response
    WF-->>BE: Result
    BE-->>FE: ChatResponse
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

## Agentic RAG Architecture (v2.0)

### LangGraph Workflow

```mermaid
graph TB
    START([Start]) --> ROUTER[Router Node<br/>🔍 Intent Classification<br/>🏢 CRM Entity Detection]
    
    ROUTER -->|intent=sql| SQL[SQL Node<br/>🗄️ Query Generation]
    ROUTER -->|intent=knowledge<br/>or intent=crm| KB[Knowledge Node<br/>📚 Hybrid Search]
    
    subgraph SQL_FLOW[SQL Processing]
        SQL --> SCHEMA[Get Schema<br/>SQLAlchemy Inspector]
        SCHEMA --> GENQ[LLM: Generate SQL]
        GENQ --> EXEC[Execute Query]
    end
    
    subgraph KB_FLOW[Knowledge Processing]
        KB --> VEC[Vector Search<br/>pgvector]
        KB --> GRAPH[Graph Search<br/>Neo4j]
    end
    
    KB -->|crm_target exists| CRM[CRM Node<br/>🏢 Live Facts]
    KB -->|no crm_target| GEN[Generator Node<br/>✍️ Answer Synthesis]
    
    subgraph CRM_FLOW[CRM Processing - CONDITIONAL]
        CRM --> ZOHO[Query Zoho CRM<br/>get_crm_facts]
    end
    
    EXEC --> GEN
    ZOHO --> GEN
    
    GEN --> END([Final Answer])
    
    style ROUTER fill:#e1f5ff
    style SQL fill:#fff4e1
    style KB fill:#e8f5e9
    style CRM fill:#ffe8e8
    style GEN fill:#f3e5f5
    style CRM_FLOW stroke-dasharray: 5 5
```

### Agent State Flow

```mermaid
stateDiagram-v2
    [*] --> RouterNode: Initial State
    
    state RouterNode {
        [*] --> ClassifyIntent
        ClassifyIntent --> SearchMetadata: SQL keywords detected
        SearchMetadata --> CheckTables: Query metadata service
        CheckTables --> SetSQLIntent: Tables found
        CheckTables --> SearchCRMEntities: No tables
        SearchCRMEntities --> SetCRMIntent: CRM entity found
        SearchCRMEntities --> SetKnowledgeIntent: No CRM entity
        ClassifyIntent --> SetKnowledgeIntent: Knowledge keywords
    }
    
    SetSQLIntent --> SQLNode
    SetKnowledgeIntent --> KnowledgeNode
    SetCRMIntent --> KnowledgeNode
    
    state SQLNode {
        [*] --> GetSchema
        GetSchema --> GenerateQuery
        GenerateQuery --> ExecuteSQL
        ExecuteSQL --> [*]
    }
    
    state KnowledgeNode {
        [*] --> VectorSearch
        [*] --> GraphSearch
        VectorSearch --> CheckCRMTarget
        GraphSearch --> CheckCRMTarget
        CheckCRMTarget --> RouteToCRM: crm_target exists
        CheckCRMTarget --> RouteToGenerator: no crm_target
    }
    
    state CRMNode {
        [*] --> GetLiveFacts
        GetLiveFacts --> FormatCRMData
        FormatCRMData --> [*]
    }
    
    SQLNode --> GeneratorNode
    RouteToCRM --> CRMNode
    RouteToGenerator --> GeneratorNode
    CRMNode --> GeneratorNode
    
    state GeneratorNode {
        [*] --> CollectContext
        CollectContext --> SynthesizeAnswer
        SynthesizeAnswer --> [*]
    }
    
    GeneratorNode --> [*]
```

### Agent Tools

| Tool | Purpose | Location |
|------|---------|----------|
| `search_knowledge_base` | Hybrid RAG (Vector+Graph) | `app/tools/knowledge.py` |
| `execute_sql_query` | Run SELECT queries | `app/tools/sql.py` |
| `get_sql_schema` | Inspect table schemas | `app/tools/sql.py` |
| `get_crm_facts` | Fetch live CRM data | `app/tools/crm.py` |
| `check_crm_status` | Check CRM availability | `app/tools/crm.py` |

### External Source Configuration

```yaml
# backend/app/config/external_sources.yaml
sources:
  - id: "erp_postgres"
    type: "sql"
    description: "Business data: revenue, customers, invoices"
    connection_env: "ERP_DATABASE_URL"
    tables:
      - name: "invoices"
        description: "Invoice records with amounts and dates"
```

**Services:**
- **MetadataService**: Discovers relevant tables based on query
- **SQLConnectorService**: Manages database connections with pooling

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
