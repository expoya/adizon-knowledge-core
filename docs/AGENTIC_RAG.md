# Adizon Enterprise-Intelligence-System
## Agentic RAG Architecture Documentation

> **Version 2.1** - Intelligentes Multi-Source RAG mit CRM-Integration

---

## 🎯 Executive Summary

Das **Adizon Enterprise-Intelligence-System** ist ein fortschrittliches, agentisches RAG-System (Retrieval-Augmented Generation), das vier Hauptdatenquellen intelligent kombiniert:

1. **📚 Interne Wissensdatenbank** (Hybrid: Vector + Graph)
2. **🗄️ Externe SQL-Datenbanken** (Strukturierte Geschäftsdaten)
3. **📞 CRM-System** (Live-Daten zu Kunden, Deals, Aktivitäten)
4. **🤖 LLM-basiertes Routing** (Intelligente Query-Klassifizierung)

### Kernmerkmale

- ✅ **Agentic Architecture**: LangGraph-basierter Workflow mit autonomer Entscheidungsfindung
- ✅ **Multi-Source Intelligence**: Vereint Dokumente, Knowledge Graphs, Datenbanken und CRM
- ✅ **Dynamic Routing**: LLM klassifiziert Queries und wählt optimale Datenquelle
- ✅ **SQL Query Generation**: Automatische SQL-Generierung aus natürlicher Sprache
- ✅ **CRM Plugin System**: Modulare, erweiterbare CRM-Integrationen (Zoho, Salesforce, etc.)
- ✅ **Entity Detection**: Automatische Erkennung von CRM-Entities in Queries
- ✅ **Live Facts**: Real-time CRM-Daten (Deals, Meetings, Objections, Finance)
- ✅ **Schema Discovery**: Intelligente Metadaten-Verwaltung für externe Quellen
- ✅ **Streaming Support**: Token-by-Token Antworten ohne Leaks
- ✅ **Enterprise-Ready**: Fehlerbehandlung, Logging, Skalierbarkeit

---

## 🏗️ System Architecture

### High-Level Overview

```mermaid
graph TB
    subgraph User["👤 User Interface"]
        UI[Frontend<br/>Chat Interface]
    end
    
    subgraph API["🚀 API Layer"]
        CHAT[Chat Endpoint<br/>/api/v1/chat]
    end
    
    subgraph Agent["🤖 Agentic RAG Core"]
        ROUTER[Router Node<br/>Intent Classification<br/>CRM Entity Detection]
        SQL[SQL Node<br/>Query Generation]
        KB[Knowledge Node<br/>Hybrid Search]
        CRM[CRM Node<br/>Live Facts<br/>CONDITIONAL]
        GEN[Generator Node<br/>Answer Synthesis]
    end
    
    subgraph Tools["🔧 Agent Tools"]
        SQLTOOL[SQL Tools<br/>execute_sql_query<br/>get_sql_schema]
        KBTOOL[Knowledge Tool<br/>search_knowledge_base]
        CRMTOOL[CRM Tool<br/>get_crm_facts]
        META[Metadata Service<br/>Source Discovery]
    end
    
    subgraph Data["💾 Data Sources"]
        VECTOR[(Vector Store<br/>pgvector)]
        GRAPH[(Knowledge Graph<br/>Neo4j)]
        ERP[(External DB<br/>ERP PostgreSQL)]
        ZOHO[(CRM System<br/>Zoho Books)]
    end
    
    UI --> CHAT
    CHAT --> ROUTER
    
    ROUTER -->|"intent=sql"| SQL
    ROUTER -->|"intent=knowledge<br/>or intent=crm"| KB
    
    SQL --> SQLTOOL
    KB --> KBTOOL
    CRM --> CRMTOOL
    
    SQLTOOL --> META
    SQLTOOL --> ERP
    KBTOOL --> VECTOR
    KBTOOL --> GRAPH
    CRMTOOL --> ZOHO
    
    SQL --> GEN
    KB -->|"if crm_target<br/>exists"| CRM
    KB -->|"else"| GEN
    CRM --> GEN
    GEN --> CHAT
    CHAT --> UI
    
    style Agent fill:#e1f5ff
    style Tools fill:#fff4e1
    style Data fill:#f0f0f0
    style CRM stroke-dasharray: 5 5
```

### Workflow Execution Flow

```mermaid
sequenceDiagram
    participant User
    participant API as Chat API
    participant Router as Router Node
    participant Meta as Metadata Service
    participant SQL as SQL Node
    participant KB as Knowledge Node
    participant CRM as CRM Node
    participant Gen as Generator Node
    participant DB as External DB
    participant Vector as Vector Store
    participant Graph as Knowledge Graph
    participant Zoho as Zoho CRM
    
    User->>API: POST /chat {"message": "..."}
    API->>Router: Execute Workflow
    
    Router->>Router: LLM Intent Classification
    Router->>Meta: get_relevant_tables(query)
    
    alt SQL Intent (Finanzielle Daten)
        Meta-->>Router: Found: "invoices" table
        Router->>Router: Set intent="sql", sql_context={...}
        Router->>SQL: Route to SQL Node
        SQL->>SQL: get_sql_schema("invoices")
        SQL->>SQL: LLM generates SQL Query
        SQL->>DB: execute_sql_query(...)
        DB-->>SQL: Query Results
        SQL->>Gen: tool_outputs["sql_result"]
    else Knowledge Intent (Dokumente/Graph)
        Meta-->>Router: No tables found
        Router->>Router: Search for CRM entities in Graph
        Router->>Graph: Query for entities with source_id
        
        alt CRM Entity Found
            Graph-->>Router: Found: "zoho_123456" (Person/Firma)
            Router->>Router: Set intent="crm", crm_target="zoho_123456"
        else No CRM Entity
            Graph-->>Router: No CRM entity found
            Router->>Router: Set intent="knowledge"
        end
        
        Router->>KB: Route to Knowledge Node
        par Hybrid Search
            KB->>Vector: Similarity Search (top 5, ≥0.8)
            Vector-->>KB: Relevant Chunks
        and
            KB->>Graph: Query Graph (Entities & Relations)
            Graph-->>KB: Graph Context
        end
        KB->>KB: Store tool_outputs["knowledge_result"]
        
        alt CRM Target exists
            KB->>CRM: Route to CRM Node
            CRM->>Zoho: get_crm_facts(entity_id)
            Zoho-->>CRM: Live CRM Data (Deals, Status, etc.)
            CRM->>Gen: tool_outputs["crm_result"]
        else No CRM Target
            KB->>Gen: tool_outputs["knowledge_result"]
        end
    end
    
    Gen->>Gen: LLM synthesizes answer
    Gen->>Gen: Combines all tool_outputs
    Gen-->>API: messages[-1] = AIMessage
    API-->>User: ChatResponse with answer
```

---

## 🧩 Component Architecture

### 1. State Management (TypedDict)

```python
class AgentState(TypedDict):
    messages: List[AnyMessage]          # Conversation history
    intent: str                         # "sql" | "knowledge" | "crm" | "general"
    sql_context: Dict[str, Any]         # {"source_id": "...", "table_names": [...]}
    crm_target: str                     # Entity ID für CRM-Abfrage (z.B. "zoho_123456")
    tool_outputs: Dict[str, str]        # {"sql_result": "...", "knowledge_result": "...", "crm_result": "..."}
```

**State Flow:**
```
INITIAL → Router (sets intent + context + crm_target) → Tools (populate outputs) → Generator → FINAL
```

**Intent Types:**
- `sql`: Finanzielle/strukturierte Daten aus externer DB
- `knowledge`: Dokument-basierte Suche (Vector + Graph)
- `crm`: Kombination aus Knowledge + Live CRM-Facts
- `general`: Allgemeine Fragen ohne spezifischen Kontext

### 2. LangGraph Nodes

#### 🔀 Router Node
**Purpose:** Query Classification, Source Discovery & CRM Entity Detection

```mermaid
flowchart TD
    START([Query]) --> LLM[LLM Classification]
    LLM --> CHECK{SQL Intent?}
    CHECK -->|Yes| META[Metadata Search]
    CHECK -->|No| GRAPH[Graph Search for CRM Entities]
    
    META --> FOUND{Tables Found?}
    FOUND -->|Yes| SQL[Set intent=sql<br/>+ sql_context]
    FOUND -->|No| GRAPH
    
    GRAPH --> ENTITY{CRM Entity<br/>with source_id?}
    ENTITY -->|Yes| CRM[Set intent=crm<br/>+ crm_target]
    ENTITY -->|No| KB[Set intent=knowledge]
    
    SQL --> END([Continue])
    CRM --> END
    KB --> END
```

**Key Features:**
- LLM-based intent classification (temperature=0.0)
- Queries `MetadataService.get_relevant_tables()` für SQL-Daten
- Sucht im Graph nach CRM-Entities (Nodes mit `source_id` wie "zoho_123456")
- Extrahiert source_id und table names für SQL-Context
- Setzt crm_target für CRM-Abfragen
- Sets workflow direction (sql → knowledge → crm → generator)

#### 🗄️ SQL Node
**Purpose:** SQL Query Generation & Execution

**Process:**
1. Fetch detailed schema via `get_sql_schema` tool
2. LLM generates PostgreSQL query (temperature=0.0)
3. Clean SQL (remove markdown code blocks)
4. Execute via `execute_sql_query` tool
5. Store result in `tool_outputs["sql_result"]`

**Safety:**
- ✅ Only SELECT queries allowed
- ✅ Result limit: 100 rows
- ✅ Comprehensive error handling
- ✅ Connection pooling with pre-ping

#### 📚 Knowledge Node
**Purpose:** Hybrid RAG Search

**Process:**
1. Call `search_knowledge_base` tool
2. Tool internally:
   - Vector search: Top 5 chunks (score ≥ 0.8)
   - Graph search: Relevant entities and relationships
3. Store combined result in `tool_outputs["knowledge_result"]`
4. Check if CRM target exists → route to CRM node or directly to generator

**Output Format:**
```
=== TEXT WISSEN ===
[Quelle 1: document.pdf, Chunk 0]
Content...

=== GRAPH WISSEN ===
ORGANIZATION: Voltage Solutions
  - HAS_DEAL -> DEAL: Solar Installation
```

#### 🏢 CRM Node (CONDITIONAL)
**Purpose:** Live CRM Data Enrichment

**Activation:** Nur wenn `crm_target` im State gesetzt ist (via Router)

**Process:**
1. Call `get_crm_facts` tool with `entity_id` (z.B. "zoho_123456")
2. Tool internally:
   - Connects to CRM system (Zoho Books)
   - Fetches live data for entity
   - Returns formatted facts (Deals, Status, Contact Info, etc.)
3. Store result in `tool_outputs["crm_result"]`

**Conditional Logic:**
```python
def should_use_crm(state: AgentState) -> str:
    intent = state.get("intent", "")
    has_target = bool(state.get("crm_target"))
    return "crm" if intent == "crm" and has_target else "skip_crm"
```

**Output Format:**
```
=== LIVE CRM FACTS ===
Entity: Max Mustermann (CONTACT)
Status: Active Customer
Last Activity: 2025-01-05
Open Deals: 2
- Deal #1: Solar Installation (€50,000)
- Deal #2: Consulting Package (€5,000)
```

#### ✍️ Generator Node
**Purpose:** Final Answer Synthesis

**Process:**
1. Collect all `tool_outputs`
2. Build comprehensive context
3. LLM generates natural language answer (temperature=0.7)
4. Integrates facts without mentioning sources explicitly

---

## 🔧 Agent Tools

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
- Formatted output with sources
- Error resilience

### SQL Tools

#### 1. Execute SQL Query

```python
@tool
def execute_sql_query(query: str, source_id: str = "erp_postgres") -> str:
    """Executes SELECT query on external database"""
```

**Features:**
- Security: Only SELECT allowed
- JSON result formatting
- 100 row limit
- Error messages as strings

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

## 📞 CRM Plugin System

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

## 📊 Data Flow Patterns

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

### Pattern 3: CRM Query with Entity Detection

```
User: "Wie steht es um Voltage Solutions?"
  ↓
Router:
  → LLM classifies as "knowledge"
  → Searches graph for "Voltage Solutions"
  → Finds node with source_id="zoho_3652397000000649013"
  → Sets intent="crm", crm_target="zoho_..."
  ↓
Knowledge Node:
  → Finds documents about Voltage Solutions
  ↓
CRM Node:
  → Calls get_crm_facts("zoho_3652397000000649013", "...")
  → Queries: Einwände, Calendly, Deals, Finance
  → Returns: Markdown with live data
  ↓
Generator:
  → Context: Documents + CRM Live Facts
  → Synthesizes comprehensive answer
  ↓
Response: "Voltage Solutions hat 3 offene Deals im Wert von €125k. 
           Letzter Call am 10.01. Haupteinwand war Preis (jetzt geklärt)..."
```

### Pattern 4: Hybrid Query (Future)

```
User: "Zeige mir alle Deals mit Voltage Solutions"
  ↓
Router: intent="hybrid"
  ↓
Parallel Execution:
  → Knowledge Node: Finds Voltage Solutions in graph
  → SQL Node: Queries deals table
  → CRM Node: Gets live CRM data
  ↓
Generator: Combines all contexts
  ↓
Response: Rich answer with graph entities + database + CRM facts
```

---

## 🗂️ Metadata Management

### External Sources Configuration

**File:** `backend/app/config/external_sources.yaml`

```yaml
sources:
  - id: "erp_postgres"
    type: "sql"
    description: "Enthält strukturierte Geschäftsdaten. Wichtig für Umsatz, Kunden und Rechnungen."
    connection_env: "ERP_DATABASE_URL"
    tables:
      - name: "invoices"
        description: "Rechnungen mit Betrag (amount), Datum und Kunden-ID."
      - name: "customers"
        description: "Kundenstammdaten mit Namen und Regionen."
```

### MetadataService

**Location:** `backend/app/services/metadata_store.py`

**Methods:**
- `get_relevant_tables(query: str) -> str`
  - Primitive word matching in descriptions
  - Returns formatted table information
  
- `get_source_by_id(source_id: str) -> Dict`
  - Lookup source configuration
  
- `get_all_sources() -> List[Dict]`
  - Returns all configured sources

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

## 🌊 Streaming Architecture

### Challenge: Leak Prevention

**Problem:** LangGraph workflows have multiple LLM calls:
- Router classification
- SQL query generation
- Final answer generation

**Solution:** Event Filtering

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

**Result:** Users only see final answer tokens, not internal reasoning.

---

## 🔐 Security & Error Handling

### SQL Security

1. **Query Validation:**
   - Only SELECT statements allowed
   - Regex check: `query.strip().upper().startswith("SELECT")`

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

## 📁 Project Structure

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

## 🚀 API Reference

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

## ⚙️ Configuration

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

## 🎓 Best Practices

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

## 🔮 Future Enhancements

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

## 📈 Performance Metrics

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

## 🐛 Troubleshooting

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

## 📚 References

- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)
- [LangChain Tools](https://python.langchain.com/docs/modules/agents/tools/)
- [FastAPI Streaming](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)
- [pgvector](https://github.com/pgvector/pgvector)
- [Neo4j](https://neo4j.com/docs/)

---

**Version:** 2.0.0  
**Last Updated:** January 2026  
**Maintainer:** Adizon Development Team

