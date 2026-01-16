# Adizon Knowledge Core - Architecture Documentation

## Overview

**Adizon Knowledge Core** (auch bekannt als **Adizon Enterprise-Intelligence-System**) ist ein fortschrittliches, agentisches RAG-System (Retrieval-Augmented Generation) mit integrierter Knowledge Graph Funktionalität, CRM-Integration und SQL-Integrationsfähigkeiten. Es kombiniert vier Hauptdatenquellen:

1. **Semantische Vektorsuche** (pgvector) für Dokumenten-Chunks
2. **Knowledge Graph** (Neo4j) für Entity-Beziehungen und Entity Resolution
3. **CRM-System** (Zoho) für Live-Kundendaten, Deals und Aktivitäten
4. **Externe SQL-Datenbanken** für strukturierte Geschäftsdaten (IoT, ERP)

Das System nutzt **LangGraph** mit einer **vereinfachten 3-Node Architektur** (Phase 3) für intelligentes, autonomes Routing und Multi-Source Intelligence.

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

### Chat Query Flow (Agentic RAG Phase 3 - Streamlined)

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant BE as Backend API
    participant WF as LangGraph Workflow
    participant ROUTER as Router Node
    participant KB as Knowledge Orchestrator
    participant META as Metadata Service
    participant GEN as Generator Node
    participant PG as PostgreSQL<br/>+ pgvector
    participant NEO as Neo4j
    participant ZOHO as Zoho CRM
    participant EXDB as External DB

    FE->>BE: POST /api/v1/chat
    BE->>WF: Execute Workflow

    WF->>ROUTER: Classify Intent
    ROUTER->>ROUTER: LLM Analysis (question/general)

    alt Intent = "general" (Small Talk)
        ROUTER->>GEN: Skip Knowledge
    else Intent = "question" (Fachfrage)
        ROUTER->>KB: Route to Knowledge Orchestrator

        Note over KB,META: Step 1: LLM-based Source Discovery
        KB->>META: get_relevant_sources_llm(query)
        META-->>KB: Relevant Sources (max 3)

        Note over KB,NEO: Step 2: Entity Resolution (wenn nötig)
        KB->>KB: LLM Entity Extraction
        KB->>NEO: Cypher Query (Fuzzy Match)
        NEO-->>KB: Entity IDs (zoho_xxx, iot_xxx)

        Note over KB: Step 3: Tool Execution
        par Parallel Tool Calls
            KB->>PG: search_knowledge_base()
            PG-->>KB: Vector + Graph Results
        and
            KB->>ZOHO: get_crm_facts(entity_id)
            ZOHO-->>KB: Live CRM Data
        and
            KB->>EXDB: execute_sql_query()
            EXDB-->>KB: SQL Results
        end

        KB->>KB: Store tool_outputs
        KB->>GEN: Combined Context
    end

    GEN->>GEN: Synthesize Answer (temp=0.7)
    GEN-->>WF: AIMessage
    WF-->>BE: Final State
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

## Agentic RAG Architecture (Phase 3 - Streamlined)

### LangGraph Workflow - Vereinfachte 3-Node Architektur

```mermaid
graph TB
    START([Start]) --> ROUTER[Router Node<br/>Intent Classification<br/>question / general]

    ROUTER -->|intent=question| KB[Knowledge Orchestrator<br/>Multi-Source Hub]
    ROUTER -->|intent=general| GEN[Generator Node<br/>Answer Synthesis]

    subgraph KB_FLOW[Knowledge Orchestrator - 4 Steps]
        KB --> DISCOVER[Step 1: LLM Source Discovery<br/>MetadataService]
        DISCOVER --> ENTITY[Step 2: Entity Resolution<br/>Graph + Fuzzy Match]
        ENTITY --> TOOLS[Step 3: Tool Execution<br/>Parallel Calls]
        TOOLS --> STORE[Step 4: Store Results<br/>tool_outputs]
    end

    subgraph TOOL_CALLS[Available Tools]
        T1[search_knowledge_base<br/>Vector + Graph]
        T2[get_crm_facts<br/>Zoho Live Data]
        T3[execute_sql_query<br/>External DBs]
    end

    TOOLS --> T1
    TOOLS --> T2
    TOOLS --> T3

    STORE --> GEN

    GEN --> END([Final Answer])

    style ROUTER fill:#e1f5ff
    style KB fill:#e8f5e9
    style GEN fill:#f3e5f5
    style KB_FLOW fill:#f0f9f0
```

### Agent State Flow

```mermaid
stateDiagram-v2
    [*] --> RouterNode: Initial State

    state RouterNode {
        [*] --> ClassifyIntent
        ClassifyIntent --> SetQuestion: Fachfrage erkannt
        ClassifyIntent --> SetGeneral: Small Talk erkannt
    }

    SetQuestion --> KnowledgeOrchestrator
    SetGeneral --> GeneratorNode

    state KnowledgeOrchestrator {
        [*] --> SourceDiscovery
        SourceDiscovery --> LLMSourceSelection: Query analysieren
        LLMSourceSelection --> EntityResolution: Sources mit entity_id
        LLMSourceSelection --> ToolExecution: Sources ohne entity_id

        state EntityResolution {
            [*] --> ExtractNames
            ExtractNames --> GraphQuery
            GraphQuery --> FuzzyMatch
            FuzzyMatch --> [*]: Entity IDs
        }

        EntityResolution --> ToolExecution

        state ToolExecution {
            [*] --> ParallelCalls
            ParallelCalls --> KnowledgeTool: knowledge_base
            ParallelCalls --> CRMTool: crm source
            ParallelCalls --> SQLTool: sql source
            KnowledgeTool --> StoreOutputs
            CRMTool --> StoreOutputs
            SQLTool --> StoreOutputs
        }

        StoreOutputs --> [*]
    }

    KnowledgeOrchestrator --> GeneratorNode

    state GeneratorNode {
        [*] --> AssembleContext
        AssembleContext --> CheckUncertainty
        CheckUncertainty --> AskClarification: entity_uncertain=true
        CheckUncertainty --> SynthesizeAnswer: confident
        AskClarification --> [*]
        SynthesizeAnswer --> [*]
    }

    GeneratorNode --> [*]
```

### Agent Tools

| Tool | Purpose | Location | Security |
|------|---------|----------|----------|
| `search_knowledge_base` | Hybrid RAG (Vector+Graph) | `app/tools/knowledge.py` | - |
| `execute_sql_query` | Run SELECT queries | `app/tools/sql.py` | sqlparse Validation, READ-ONLY User |
| `get_sql_schema` | Inspect table schemas | `app/tools/sql.py` | - |
| `get_crm_facts` | Fetch live CRM data | `app/tools/crm.py` | OAuth2 Token Refresh |
| `check_crm_status` | Check CRM availability | `app/tools/crm.py` | - |

### SQL Security (Defense-in-Depth)

Das SQL-Tool verwendet mehrere Sicherheitsebenen:

1. **sqlparse Validation:**
   - Nur 1 Statement (kein Statement Stacking)
   - Nur SELECT (Whitelist)
   - Keine UNION, INFORMATION_SCHEMA
   - Keine SQL-Comments (-- oder /*)
   - Keine Always-True Patterns (1=1)
   - Keine Time-Based Injection (SLEEP, WAITFOR)

2. **Database Level:**
   - Dedizierter READ-ONLY User (`sql_tool_reader`)
   - GRANT SELECT only
   - Max 100 Rows Limit

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
