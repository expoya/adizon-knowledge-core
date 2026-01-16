# Adizon Enterprise-Intelligence-System
## Agentic RAG Architecture Documentation

> **Version 3.0 (Phase 3)** - Streamlined 3-Node Architecture mit LLM-basierter Source Discovery

---

## Executive Summary

Das **Adizon Enterprise-Intelligence-System** ist ein fortschrittliches, agentisches RAG-System (Retrieval-Augmented Generation) mit einer **vereinfachten 3-Node Architektur**, das vier Hauptdatenquellen intelligent kombiniert:

1. **Interne Wissensdatenbank** (Hybrid: Vector + Graph)
2. **Externe SQL-Datenbanken** (IoT, ERP, strukturierte Geschäftsdaten)
3. **CRM-System** (Live-Daten zu Kunden, Deals, Aktivitäten via Zoho)
4. **LLM-basierte Source Discovery** (Intelligente Auswahl relevanter Quellen)

### Kernmerkmale (Phase 3)

- **Streamlined Architecture**: 3 Nodes statt 5+ (Router → Knowledge Orchestrator → Generator)
- **LLM Source Discovery**: Intelligente Auswahl der relevanten Datenquellen via MetadataService
- **Entity Resolution**: Graph-basierte Fuzzy-Match Entity-Erkennung (70% Threshold)
- **Multi-Source Intelligence**: Parallele Tool-Ausführung für Knowledge, CRM und SQL
- **Unified Knowledge Orchestrator**: Ein Node koordiniert alle Datenquellen
- **SQL Security**: Defense-in-Depth mit sqlparse Validation + READ-ONLY DB User
- **CRM Plugin System**: Modulare, erweiterbare CRM-Integrationen (Zoho implementiert)
- **Streaming Support**: Token-by-Token Antworten mit Event-Filtering
- **Entity Uncertainty Handling**: Bei niedrigem Match-Score → User-Rückfrage

---

## System Architecture

### High-Level Overview (Phase 3 - Streamlined)

```mermaid
graph TB
    subgraph User["User Interface"]
        UI[Frontend<br/>Chat Interface]
    end

    subgraph API["API Layer"]
        CHAT[Chat Endpoint<br/>/api/v1/chat]
    end

    subgraph Agent["Agentic RAG Core - 3 Nodes"]
        ROUTER[Router Node<br/>Intent: question/general]
        KB[Knowledge Orchestrator<br/>Multi-Source Hub]
        GEN[Generator Node<br/>Answer Synthesis]
    end

    subgraph KBSteps["Knowledge Orchestrator Steps"]
        S1[1. LLM Source Discovery]
        S2[2. Entity Resolution]
        S3[3. Tool Execution]
        S4[4. Store Results]
    end

    subgraph Tools["Agent Tools"]
        KBTOOL[search_knowledge_base<br/>Vector + Graph]
        CRMTOOL[get_crm_facts<br/>Live CRM Data]
        SQLTOOL[execute_sql_query<br/>External DBs]
    end

    subgraph Data["Data Sources"]
        VECTOR[(pgvector)]
        GRAPH[(Neo4j)]
        ZOHO[(Zoho CRM)]
        ERP[(External SQL)]
    end

    UI --> CHAT
    CHAT --> ROUTER

    ROUTER -->|"intent=question"| KB
    ROUTER -->|"intent=general"| GEN

    KB --> S1 --> S2 --> S3 --> S4

    S3 --> KBTOOL
    S3 --> CRMTOOL
    S3 --> SQLTOOL

    KBTOOL --> VECTOR
    KBTOOL --> GRAPH
    CRMTOOL --> ZOHO
    SQLTOOL --> ERP

    S4 --> GEN
    GEN --> CHAT
    CHAT --> UI

    style Agent fill:#e1f5ff
    style KBSteps fill:#e8f5e9
    style Tools fill:#fff4e1
    style Data fill:#f0f0f0
```

### Workflow Execution Flow (Phase 3)

```mermaid
sequenceDiagram
    participant User
    participant API as Chat API
    participant Router as Router Node
    participant KB as Knowledge Orchestrator
    participant Meta as Metadata Service
    participant Gen as Generator Node
    participant Vector as Vector Store
    participant Graph as Neo4j
    participant Zoho as Zoho CRM
    participant DB as External DB

    User->>API: POST /chat {"message": "..."}
    API->>Router: Execute Workflow

    Router->>Router: LLM Intent Classification
    Note over Router: temperature=0.0

    alt Intent = "general" (Small Talk)
        Router->>Gen: Skip Knowledge Orchestrator
    else Intent = "question" (Fachfrage)
        Router->>KB: Route to Knowledge Orchestrator

        Note over KB,Meta: Step 1: LLM Source Discovery
        KB->>Meta: get_relevant_sources_llm(query)
        Meta-->>KB: Relevant Sources (max 3)
        Note over KB: z.B. [knowledge_base, crm_zoho, iot_timescale]

        Note over KB,Graph: Step 2: Entity Resolution
        KB->>KB: LLM extracts entity names from query
        KB->>Graph: Cypher Query (2-stage: exact + fuzzy)
        Graph-->>KB: Entity IDs (zoho_xxx, iot_xxx)
        Note over KB: Fuzzy Match >= 70% Threshold

        Note over KB: Step 3: Parallel Tool Execution
        par Knowledge Base
            KB->>Vector: search_knowledge_base()
            Vector-->>KB: Chunks (score >= 0.8)
            KB->>Graph: Graph Search
            Graph-->>KB: Entities & Relations
        and CRM (wenn Entity gefunden)
            KB->>Zoho: get_crm_facts(entity_id)
            Zoho-->>KB: Live CRM Data
        and SQL (wenn Source relevant)
            KB->>DB: execute_sql_query()
            DB-->>KB: SQL Results (max 100 rows)
        end

        Note over KB: Step 4: Store Results
        KB->>KB: tool_outputs = {knowledge, crm, sql}
        KB->>Gen: Combined Context
    end

    Note over Gen: Assemble Context + Generate
    Gen->>Gen: Check entity_uncertain flag
    alt entity_uncertain = true
        Gen->>Gen: Generate clarification request
    else Confident
        Gen->>Gen: LLM synthesizes answer (temp=0.7)
    end
    Gen-->>API: AIMessage
    API-->>User: ChatResponse
```

---

## Component Architecture

### 1. State Management (TypedDict)

```python
class AgentState(TypedDict):
    messages: List[AnyMessage]          # Conversation history (HumanMessage, AIMessage)
    intent: str                         # "question" | "general"
    crm_target: str                     # Entity ID für CRM (z.B. "zoho_123456", "iot_sensor_001")
    tool_outputs: Dict[str, str]        # {
                                        #     "knowledge_result": "...",
                                        #     "crm_result": "...",
                                        #     "sql_result": "..."
                                        # }
    entity_uncertain: bool              # Optional: Flag für niedrigen Match-Score
```

**State Flow (Phase 3):**
```
INITIAL → Router (sets intent) → Knowledge Orchestrator (source discovery + entity resolution + tools) → Generator → FINAL
```

**Intent Types (Vereinfacht):**
- `question`: Fachfrage → Knowledge Orchestrator
- `general`: Small Talk → Direkt zum Generator (Skip Knowledge)

### 2. LangGraph Nodes (Phase 3 - Vereinfacht auf 3 Nodes)

#### Router Node
**Purpose:** Reine Intent-Klassifikation

```mermaid
flowchart TD
    START([Query]) --> LLM[LLM Classification<br/>temp=0.0]
    LLM --> CHECK{Intent?}
    CHECK -->|Fachfrage| QUESTION[Set intent=question]
    CHECK -->|Small Talk| GENERAL[Set intent=general]
    QUESTION --> KB([Knowledge Orchestrator])
    GENERAL --> GEN([Generator])
```

**Key Features:**
- LLM-based intent classification (temperature=0.0)
- Nur 2 Intent-Typen: `question` oder `general`
- Keine Entity Resolution im Router (verschoben zu Knowledge Orchestrator)
- Fallback bei Fehler: `question`

#### Knowledge Orchestrator Node (Zentraler Hub)
**Purpose:** Intelligente Multi-Source Daten-Orchestrierung

**4-Schritt Prozess:**

**Step 1: LLM Source Discovery**
```python
relevant_sources = metadata_service.get_relevant_sources_llm(query)
# Returns: max 3 Sources (z.B. [knowledge_base, crm_zoho, iot_timescale])
```
- Wählt relevante Sources basierend auf Keywords, Modules, Tables
- Fallback: nur `knowledge_base` bei LLM-Fehler

**Step 2: Entity Resolution**
- Nur für Sources mit `requires_entity_id=True`
- LLM extrahiert Entity-Namen aus Query
- 2-Stufen Cypher-Query:
  1. Exact Match (Score: 100)
  2. Partial Match mit CONTAINS (Score: 50)
- Fuzzy Matching bei Score >= 60 (70% Threshold)
- Output: Entity IDs (z.B. `zoho_12345`, `iot_sensor_001`)

**Step 3: Tool Execution (Parallel)**

| Source Type | Tool | Input |
|-------------|------|-------|
| `knowledge_base` | `search_knowledge_base()` | Query |
| CRM Source | `get_crm_facts()` | entity_id |
| SQL Source | `execute_sql_query()` | equipment_id |

**Step 4: Store Results**
```python
state["tool_outputs"] = {
    "knowledge_result": "...",
    "crm_result": "...",
    "sql_result": "..."
}
```

#### Generator Node
**Purpose:** Finale Antwort-Synthese

**Process:**
1. Kontext-Assemblierung (Chat-History, alle tool_outputs)
2. Check `entity_uncertain` Flag
3. Bei Unsicherheit: Clarification Request statt Antwort
4. LLM-Generierung (temperature=0.7)
5. Company Context aus MinIO (5min Cache)

---

## Agent Tools

### Knowledge Tool

```python
@tool
async def search_knowledge_base(query: str) -> str:
    """Searches internal knowledge base (Vector + Graph)"""
```

**Location:** `backend/app/tools/knowledge.py`

**Features:**
- Async execution
- Hybrid search (pgvector + Neo4j)
- Top 5 Chunks mit Similarity Score >= 0.8
- Formatted output with sources

**Output Format:**
```
=== TEXT WISSEN (Relevante Dokument-Abschnitte) ===
[Quelle 1: document.pdf, Chunk 5]
... Content ...

=== GRAPH WISSEN (Entitäten und Beziehungen) ===
ORGANIZATION: Voltage Solutions
  - HAS_DEAL -> DEAL: Solar Installation
```

### SQL Tools

#### 1. Execute SQL Query

```python
@tool
def execute_sql_query(query: str, source_id: str = "erp_postgres") -> str:
    """Executes SELECT query on external database"""
```

**Security (Defense-in-Depth mit sqlparse):**
- Nur 1 Statement (kein Statement Stacking)
- Nur SELECT (Whitelist)
- Keine UNION, INFORMATION_SCHEMA
- Keine SQL-Comments (-- oder /*)
- Keine Always-True Patterns (1=1)
- Keine Time-Based Injection (SLEEP, WAITFOR)
- Database-Level: READ-ONLY User (`sql_tool_reader`)
- Max 100 Rows Limit

#### 2. Get SQL Schema

```python
@tool
def get_sql_schema(source_id: str = "erp_postgres", table_names: List[str] = None) -> str:
    """Retrieves detailed schema information"""
```

**Returns:**
- Column names and types
- Nullable constraints
- Primary keys
- Foreign key relationships

### CRM Tools

#### 1. Get CRM Facts

```python
@tool
async def get_crm_facts(entity_id: str, query_context: str = "") -> str:
    """Retrieves live facts about an entity from CRM"""
```

**Location:** `backend/app/tools/crm.py`

**Features:**
- CRM availability check
- Live data retrieval
- Multi-module queries (Deals, Meetings, Objections, Finance)
- Markdown-formatted output
- Error handling with graceful degradation

**Example:**
```python
facts = await get_crm_facts(
    entity_id="zoho_3652397000000649013",
    query_context="deals and revenue information"
)
```

**Returns:**
```markdown
# Live Facts for Entity: zoho_3652397000000649013

### 💰 Deals
- **Solar Installation**: €50,000.00 | Proposal | Close: 2026-02-01
- **Maintenance Contract**: €5,000.00 | Negotiation | Close: 2026-01-15

**Total Deal Value**: €55,000.00

### 📅 Calendly Events
- **Demo Call**: 2026-01-10 14:00 (Status: Scheduled)

### 🛡️ Einwände
- **Preis zu hoch**: (Status: Geklärt)
```

#### 2. Check CRM Status

```python
@tool
def check_crm_status() -> str:
    """Checks if CRM is configured and reachable"""
```

**Returns:** Status string with provider name or error

---

## CRM Plugin System

### Architecture

Das CRM-Plugin-System ermöglicht modulare Integration verschiedener CRM-Systeme ohne Core-Dependencies.

```
Core (Agnostic)
    ↓
CRMProvider Interface (Abstract)
    ↓
Factory Pattern (crm_factory.py)
    ↓
Concrete Implementations (zoho/, salesforce/, ...)
```

### CRMProvider Interface

Alle CRM-Provider müssen dieses Interface implementieren:

```python
class CRMProvider(ABC):
    @abstractmethod
    def check_connection() -> bool
    
    @abstractmethod
    def fetch_skeleton_data(entity_types: list[str]) -> list[dict]
    
    @abstractmethod
    def search_live_facts(entity_id: str, query_context: str) -> str
    
    @abstractmethod
    def execute_raw_query(query: str) -> Any
    
    @abstractmethod
    def get_provider_name() -> str
    
    @abstractmethod
    def get_available_modules() -> list[str]
```

### Zoho CRM Provider

**Status:** ✅ Fully Implemented

**Features:**
- OAuth2 Refresh Token Flow
- Automatic token refresh (1-hour cache)
- COQL (CRM Object Query Language) support
- Multi-module live facts:
  - Einwände (Objections)
  - Calendly Events
  - Deals with fallback relations
  - Finance/Subscriptions

**Example:**
```python
provider = ZohoCRMProvider(
    client_id="1000.ABC123",
    client_secret="secret",
    refresh_token="1000.refresh.token",
    api_base_url="https://www.zohoapis.eu"
)

# Check connection
if provider.check_connection():
    # Fetch skeleton data for graph
    entities = provider.fetch_skeleton_data(["Contacts", "Accounts"])
    
    # Get live facts
    facts = provider.search_live_facts("zoho_123456", "deals")
```

### CRM Factory

```python
from app.services.crm_factory import get_crm_provider, is_crm_available

# Check availability
if is_crm_available():
    provider = get_crm_provider()
    provider_name = provider.get_provider_name()
```

**Supported Providers:**
- ✅ **Zoho CRM** - Fully implemented
- 🔜 **Salesforce** - Planned
- 🔜 **HubSpot** - Planned
- 🔜 **Microsoft Dynamics** - Planned

### CRM Sync Endpoint

**Endpoint:** `POST /api/v1/ingestion/crm-sync`

Synchronisiert CRM-Entities in den Knowledge Graph für Entity Detection.

**Request:**
```json
{
  "entity_types": ["Contacts", "Accounts", "Leads"]
}
```

**Response:**
```json
{
  "status": "success",
  "entities_synced": 150,
  "entities_created": 120,
  "entities_updated": 30,
  "entity_types": ["Contact", "Account", "Lead"],
  "message": "Successfully synced 150 entities from Zoho CRM"
}
```

**Use Cases:**
- Initial setup: Populate graph with CRM entities
- Nightly cron job: Keep graph synchronized
- Manual trigger: After major CRM updates

---

## Data Flow Patterns

### Pattern 1: Knowledge Query

```
User: "Was ist unsere Sicherheitsrichtlinie?"
  ↓
Router: intent="knowledge"
  ↓
Knowledge Node:
  → Vector: Finds "Sicherheitsrichtlinie" document chunks
  → Graph: No relevant entities
  ↓
Generator: Synthesizes answer from document chunks
  ↓
Response: "Unsere Sicherheitsrichtlinie besagt..."
```

### Pattern 2: SQL Query

```
User: "Welche Rechnungen haben wir im Dezember?"
  ↓
Router: 
  → LLM: "sql" intent
  → Metadata: Finds "invoices" table in "erp_postgres"
  ↓
SQL Node:
  → Schema: Gets "invoices" columns (amount, date, customer_id)
  → LLM: Generates "SELECT * FROM invoices WHERE date >= '2024-12-01'"
  → Execute: Returns results
  ↓
Generator: Formats results as natural answer
  ↓
Response: "Im Dezember wurden 5 Rechnungen erstellt: ..."
```

### Pattern 3: CRM Query with Entity Detection (Phase 3)

```
User: "Wie steht es um Voltage Solutions?"
  ↓
Router: intent="question"
  ↓
Knowledge Orchestrator:
  → Step 1: LLM Source Discovery
    → Findet: [knowledge_base, crm_zoho]
  → Step 2: Entity Resolution
    → LLM extrahiert: "Voltage Solutions"
    → Graph Query (Exact + Fuzzy Match)
    → Findet: zoho_3652397000000649013 (Score: 100)
  → Step 3: Parallel Tool Execution
    → search_knowledge_base() → Dokumente
    → get_crm_facts(entity_id) → Live CRM Data
  ↓
Generator:
  → Context: Documents + CRM Live Facts
  → Synthesizes comprehensive answer
  ↓
Response: "Voltage Solutions hat 3 offene Deals im Wert von €125k.
           Letzter Call am 10.01. Haupteinwand war Preis (jetzt geklärt)..."
```

### Pattern 4: Multi-Source Query (IoT + Knowledge)

```
User: "Wie performt die Anlage bei Müller GmbH?"
  ↓
Router: intent="question"
  ↓
Knowledge Orchestrator:
  → Step 1: LLM Source Discovery
    → Findet: [knowledge_base, iot_timescale]
  → Step 2: Entity Resolution
    → LLM extrahiert: "Müller GmbH"
    → Graph Query → Findet: iot_sensor_42 (Equipment)
  → Step 3: Parallel Tool Execution
    → search_knowledge_base() → Anlagendoku
    → execute_sql_query(WHERE machine_id='iot_sensor_42')
  ↓
Generator: Combines docs + IoT metrics
  ↓
Response: "Die Anlage bei Müller GmbH läuft mit 95% Effizienz..."
```

---

## Metadata Management

### External Sources Configuration (Phase 3 - LLM-based Discovery)

**File:** `backend/app/config/external_sources.yaml`

```yaml
sources:
  - id: "knowledge_base"
    type: "internal"
    description: "Interne Wissensdatenbank mit Dokumenten und Graph"
    tool: "search_knowledge_base"
    keywords: ["dokument", "wissen", "information"]
    requires_entity_id: false

  - id: "crm_zoho"
    type: "crm"
    description: "CRM mit Kundeninformationen, Deals, Aktivitäten"
    tool: "get_crm_facts"
    keywords: ["kunde", "deal", "kontakt", "firma"]
    modules: ["Contacts", "Accounts", "Deals"]
    requires_entity_id: true

  - id: "iot_timescale"
    type: "sql"
    description: "IoT-Sensordaten und Anlagenmetriken"
    tool: "execute_sql_query"
    connection_env: "IOT_DATABASE_URL"
    tables:
      - name: "sensor_data"
        description: "Echtzeit-Sensormessungen"
    requires_entity_id: true
```

### MetadataService (LLM-basiert)

**Location:** `backend/app/services/metadata_store.py`

**Neue Methode (Phase 3):**
```python
def get_relevant_sources_llm(query: str, max_sources: int = 3) -> List[Dict]
```
- LLM analysiert Query gegen alle Source-Beschreibungen
- Wählt max. 3 relevante Sources
- Berücksichtigt: keywords, modules, tables, description
- Fallback: nur `knowledge_base` bei Fehler

**Legacy-Methoden:**
- `get_relevant_tables(query: str)` - Primitive word matching
- `get_source_by_id(source_id: str)` - Source-Lookup
- `get_all_sources()` - Alle Sources

**Pattern:** Singleton via `@lru_cache`

### SQLConnectorService

**Location:** `backend/app/services/sql_connector.py`

**Features:**
- Engine caching per source_id
- Connection pooling (size=5, max_overflow=10)
- Pre-ping for health checks
- Environment-based connection URLs

**Usage:**
```python
connector = get_sql_connector_service()
engine = connector.get_engine("erp_postgres")
```

---

## Streaming Architecture

### Challenge: Leak Prevention

**Problem:** LangGraph workflows have multiple LLM calls:
- Router classification (temp=0.0)
- Entity Extraction (temp=0.0)
- Final answer generation (temp=0.7)

**Solution:** Event Filtering auf Generator Node

```python
async for event in chat_workflow.astream_events(inputs, version="v2"):
    event_type = event.get("event")
    event_name = event.get("name", "")

    # Track node entry/exit
    if "generator" in event_name.lower():
        in_generator = (event_type == "on_chain_start")

    # Stream ONLY generator tokens
    if event_type == "on_chat_model_stream" and in_generator:
        yield f"data: {chunk.content}\n\n"
```

**Result:** Users sehen nur finale Antwort-Tokens, keine internen Reasoning-Steps.

---

## Security & Error Handling

### SQL Security (Defense-in-Depth)

1. **sqlparse Validation (Application Level):**
   - Genau 1 Statement (kein Statement Stacking)
   - Nur SELECT (Whitelist)
   - Keine UNION (verhindert Daten-Exfiltration)
   - Keine INFORMATION_SCHEMA (Schema-Enumeration unmöglich)
   - Keine SQL-Comments (-- oder /*)
   - Keine Always-True Patterns (1=1, etc.)
   - Keine Time-Based Blind Injection (SLEEP, WAITFOR, pg_sleep)

2. **Database Level:**
   - Dedizierter READ-ONLY User (`sql_tool_reader`)
   - GRANT SELECT only auf spezifische Tables
   - SQL Injection unmöglich, selbst wenn Validation bypass

2. **Result Limiting:**
   - Maximum 100 rows returned
   - Prevents memory overflow

3. **Connection Security:**
   - Credentials from environment variables
   - No hardcoded credentials
   - Connection pooling with timeouts

### Error Handling Strategy

```mermaid
flowchart TD
    START[Tool Execution] --> TRY{Try Block}
    TRY -->|Success| RESULT[Return Result String]
    TRY -->|ValueError| CONFIG[Config Error:<br/>Source not found]
    TRY -->|SQLError| SQL[SQL Error:<br/>Query failed]
    TRY -->|Exception| GENERIC[Generic Error:<br/>Unknown issue]
    
    CONFIG --> STRING[Return Error String]
    SQL --> STRING
    GENERIC --> STRING
    STRING --> LOG[Log with traceback]
    LOG --> END[Agent continues]
    RESULT --> END
    
    style STRING fill:#ffcccc
    style END fill:#ccffcc
```

**Philosophy:** Tools return error strings, not exceptions
- Allows agent to adapt
- Provides context to LLM
- Maintains workflow continuity

---

## Project Structure

```
backend/app/
├── api/endpoints/
│   ├── chat.py              # 🔄 NEW: Workflow integration
│   ├── ingestion.py
│   └── graph.py
├── core/
│   ├── config.py
│   └── llm.py               # ✨ NEW: LLM factory
├── graph/
│   ├── chat_workflow.py     # ✨ NEW: LangGraph workflow
│   └── ingestion_workflow.py
├── tools/                   # ✨ NEW: Agent tools
│   ├── knowledge.py         # Knowledge base search
│   └── sql.py               # SQL execution + schema
├── services/
│   ├── metadata_store.py    # ✨ NEW: Source metadata
│   ├── sql_connector.py     # ✨ NEW: DB connections
│   ├── vector_store.py
│   ├── graph_store.py
│   └── storage.py
├── config/
│   ├── external_sources.yaml # ✨ NEW: Source config
│   └── ontology_voltage.yaml
└── models/
    └── document.py
```

---

## API Reference

### POST /api/v1/chat

**Request:**
```json
{
  "message": "Welche Rechnungen haben wir im Dezember?",
  "history": [
    {"role": "user", "content": "Hallo"},
    {"role": "assistant", "content": "Hallo! Wie kann ich helfen?"}
  ]
}
```

**Response:**
```json
{
  "answer": "Im Dezember 2024 wurden 5 Rechnungen erstellt...",
  "sources": ["document.pdf (Chunk 2)"],
  "graph_context": "ORGANIZATION: Voltage Solutions...",
  "vector_context": "Relevante Textabschnitte..."
}
```

### POST /api/v1/chat/stream

**Request:** Same as `/chat`

**Response:** Server-Sent Events (SSE)
```
data: Im
data:  Dezember
data:  wurden
data:  5
data:  Rechnungen
...
data: [DONE]
```

---

## Configuration

### Environment Variables

```bash
# === Internal Knowledge Base ===
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=knowledge_core
NEO4J_URI=bolt://localhost:7687

# === External Databases ===
ERP_DATABASE_URL=postgresql://user:pass@erp-host:5432/erp_db

# === AI Services ===
EMBEDDING_API_URL=http://localhost:8001/v1
EMBEDDING_API_KEY=your-key
EMBEDDING_MODEL=jina/jina-embeddings-v2-base-de
LLM_MODEL_NAME=adizon-ministral

# === MinIO ===
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

### Metadata Configuration

Edit `backend/app/config/external_sources.yaml`:

```yaml
sources:
  - id: "crm_mysql"
    type: "sql"
    description: "CRM Database with customer interactions"
    connection_env: "CRM_DATABASE_URL"
    tables:
      - name: "contacts"
        description: "Customer contact information"
      - name: "activities"
        description: "Customer interaction logs"
```

---

## Best Practices

### 1. Table Descriptions
Write clear, keyword-rich descriptions:
```yaml
# ✅ Good
description: "Rechnungen mit Betrag, Datum, Kunden-ID und Zahlungsstatus"

# ❌ Bad
description: "Invoice table"
```

### 2. Intent Classification Prompts
Keep classification prompts focused:
- Clear categories
- Keyword examples
- Single-word responses

### 3. SQL Generation
- Provide detailed schemas
- Use temperature=0.0 for consistency
- Validate and sanitize queries

### 4. Error Messages
Return descriptive error strings:
```python
return f"Error: Table '{table_name}' not found in source '{source_id}'"
```

---

## Future Enhancements

### Phase 4: True Hybrid Mode
- Parallel execution of SQL + Knowledge nodes
- Cross-source join capabilities
- Unified context ranking

### Phase 5: Advanced Features
- [ ] Query result caching
- [ ] Multi-step SQL reasoning
- [ ] Schema evolution tracking
- [ ] User feedback loop
- [ ] Query optimization hints

### Phase 6: Enterprise Features
- [ ] Role-based access control (RBAC)
- [ ] Audit logging
- [ ] Query cost estimation
- [ ] Custom tool registration
- [ ] Multi-tenant isolation

---

## Performance Metrics

### Typical Query Times

| Query Type | Average Latency | Components |
|------------|----------------|------------|
| Knowledge-only | 2-4s | Vector (0.5s) + Graph (0.5s) + LLM (2s) |
| SQL-only | 3-5s | Router (1s) + Schema (0.5s) + Gen (1s) + Exec (0.5s) + LLM (2s) |
| Hybrid | 5-7s | All combined |

### Optimization Targets
- Vector search: 99% < 1s
- SQL execution: 95% < 2s  
- LLM generation: Streaming improves perceived latency

---

## Troubleshooting

### Issue: "No relevant tables found"

**Cause:** Query keywords don't match table descriptions

**Solution:** Improve descriptions in `external_sources.yaml`

### Issue: SQL Query fails

**Cause:** Schema mismatch or invalid SQL

**Solution:** 
1. Check `get_sql_schema` output
2. Verify column names
3. Review LLM-generated query in logs

### Issue: Streaming stops mid-response

**Cause:** Generator node not properly tracked

**Solution:** Check event filtering logic in `chat_stream()`

---

## References

- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)
- [LangChain Tools](https://python.langchain.com/docs/modules/agents/tools/)
- [FastAPI Streaming](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)
- [pgvector](https://github.com/pgvector/pgvector)
- [Neo4j](https://neo4j.com/docs/)
- [sqlparse](https://sqlparse.readthedocs.io/)

---

**Version:** 3.0.0 (Phase 3 - Streamlined)
**Last Updated:** January 2026
**Maintainer:** Adizon Development Team

