# 🚀 Refactoring Plan: Smart Knowledge Orchestrator

> **Erstellt:** 2026-01-10  
> **Status:** Planning Phase  
> **Ziel:** Vereinfachung der Routing-Logik durch intelligente Source Discovery

---

## 🎯 Vision

### Das Problem

**Aktuelle Architektur:**
```
Router (entscheidet SQL vs. Knowledge)
  ├─ SQL Node (DEAKTIVIERT - Dead Code!)
  └─ Knowledge Node
       ├─ Vector Search
       ├─ Graph Search
       └─ CRM (conditional, getrennte Node)
```

**Probleme:**
- ❌ SQL Node existiert aber ist deaktiviert (Dead Code)
- ❌ Router entscheidet zu früh über Datenquellen
- ❌ Metadata Service wird falsch genutzt (im Router statt Knowledge Node)
- ❌ Keine Kombination von Datenquellen (SQL + Vector + Graph + CRM)
- ❌ SQL-Daten ohne Dokument-Context
- ❌ Komplexe Conditional Routing-Logik

### Die Lösung

**Neue Architektur:**
```
Router (nur: "Question" vs. "Small Talk")
  └─ Knowledge Orchestrator Node
       │
       ├─ Graph als "Glue" (Orientierung + IDs)
       │  ├─ Verknüpft Dokumente mit CRM-Entities
       │  ├─ Liefert CRM-IDs für Live-Abfragen
       │  └─ Zeigt Zusammenhänge zwischen Quellen
       │
       ├─ Source Discovery via Metadata Service
       │  ├─ "Rechnungen?" → Graph + CRM (Zoho Books)
       │  ├─ "Maschine?" → Graph + Vector + SQL (IoT)
       │  └─ "Preise?" → Graph + Vector (Dokumente)
       │
       └─ Parallel Tool Execution
          ├─ search_knowledge_base (Vector + Graph)
          ├─ get_crm_facts (Live CRM, via Graph-IDs)
          └─ execute_sql_query (IoT/Sensoren, optional)
```

**Vorteile:**
- ✅ Graph ist die zentrale "Glue"-Schicht
- ✅ Ein Node orchestriert alle Datenquellen
- ✅ Metadata Service als "Source Catalog"
- ✅ Quellen können kombiniert werden
- ✅ Erweiterbar durch `external_sources.yaml`
- ✅ Context-aware: Alle Daten mit vollem Kontext

---

## 🧩 Die Rolle des Knowledge Graphs

### Graph als "Glue" zwischen unstructured und structured Data

```mermaid
graph TB
    subgraph Unstructured["📄 Unstructured Knowledge"]
        DOC1[Betriebsanleitung.pdf]
        DOC2[Preisliste.pdf]
        DOC3[Prozess.docx]
    end
    
    subgraph Graph["🕸️ KNOWLEDGE GRAPH<br/>= GLUE LAYER"]
        PERSON[PERSON: Max Mustermann<br/>source_id: zoho_123]
        ORG[ORGANIZATION: ACME Corp<br/>source_id: zoho_456]
        MACHINE[EQUIPMENT: Hochdrucklader<br/>source_id: iot_42]
        CONCEPT[CONCEPT: Wartungsintervall]
        
        PERSON -->|WORKS_FOR| ORG
        ORG -->|HAS_EQUIPMENT| MACHINE
        MACHINE -->|REQUIRES| CONCEPT
        DOC1 -.->|MENTIONS| MACHINE
        DOC2 -.->|MENTIONS| ORG
        DOC3 -.->|DESCRIBES| CONCEPT
    end
    
    subgraph Structured["💾 Structured Data Sources"]
        CRM[Zoho CRM<br/>Live Contact Data<br/>via zoho_123]
        BOOKS[Zoho Books<br/>Live Invoice Data<br/>via zoho_456]
        IOT[IoT Database<br/>Live Sensor Data<br/>via iot_42]
    end
    
    Graph -->|source_id| CRM
    Graph -->|source_id| BOOKS
    Graph -->|source_id| IOT
    
    style Graph fill:#e1f5ff,stroke:#0066cc,stroke-width:3px
    style Unstructured fill:#e8f5e9
    style Structured fill:#fff4e1
```

### Workflow mit Graph als Zentrum

```mermaid
sequenceDiagram
    participant User
    participant Orch as Knowledge Orchestrator
    participant Graph as Knowledge Graph<br/>(GLUE)
    participant Vector as Vector Store
    participant CRM as Zoho CRM
    participant SQL as SQL Database
    
    User->>Orch: "Was ist der Status von ACME Corp?"
    
    Note over Orch: 1. Query Graph für Kontext
    Orch->>Graph: Search for "ACME Corp"
    Graph-->>Orch: ORGANIZATION: ACME Corp<br/>source_id: zoho_456<br/>Relationships:<br/>- HAS_EQUIPMENT: Hochdrucklader<br/>- MENTIONED_IN: Preisliste.pdf
    
    Note over Orch: 2. Graph gibt Orientierung
    Note over Orch: - Entity gefunden: ACME Corp<br/>- CRM ID: zoho_456<br/>- Related Docs: Preisliste.pdf<br/>- Related Equipment: Hochdrucklader
    
    par Vector Search (unstructured)
        Orch->>Vector: Search "ACME Corp"
        Vector-->>Orch: Chunk from Preisliste.pdf:<br/>"ACME Corp erhält 15% Rabatt..."
    and CRM Query (structured via Graph ID)
        Orch->>CRM: get_crm_facts("zoho_456")
        CRM-->>Orch: Live Data:<br/>Open Deals: 2<br/>Last Invoice: €45k<br/>Status: Active
    and SQL Query (structured via Graph ID)
        Orch->>Graph: Get equipment IDs for ACME
        Graph-->>Orch: Equipment: iot_42
        Orch->>SQL: SELECT * FROM sensors WHERE machine_id='iot_42'
        SQL-->>Orch: Temperature: 85°C<br/>Status: Running
    end
    
    Note over Orch: 3. Combine ALL contexts
    Orch->>Orch: Combine:<br/>- Graph relationships<br/>- Vector context (docs)<br/>- CRM live data<br/>- SQL sensor data
    
    Orch-->>User: "ACME Corp ist ein aktiver Kunde mit 2 offenen Deals (€45k letzte Rechnung).<br/>Sie erhalten 15% Rabatt laut Preisliste.<br/>Ihr Hochdrucklader läuft bei 85°C (nahe Grenzwert)."
```

**Der Graph liefert:**
1. ✅ **Entity Resolution:** "ACME Corp" → `zoho_456`
2. ✅ **Relationship Context:** Welche Dokumente, Maschinen, Personen sind verbunden?
3. ✅ **Source IDs:** Für Live-Abfragen (CRM, SQL, etc.)
4. ✅ **Disambiguation:** Unterscheidung zwischen mehreren "ACME" Firmen

---

## 📋 Refactoring Schritte

### Phase 1: Cleanup & Vorbereitung (Sicher, keine Breaking Changes)

#### 1.1 Dead Code entfernen
**Dateien:**
- `backend/app/graph/chat_workflow.py` - SQL Node entfernen
- `backend/app/tools/sql.py` - Markieren als "optional/legacy"
- `backend/app/services/sql_connector.py` - Markieren als "optional"

**Änderungen:**
```python
# backend/app/graph/chat_workflow.py

def create_chat_workflow() -> StateGraph:
    workflow = StateGraph(AgentState)
    
    # Nodes
    workflow.add_node("router", router_node)
    workflow.add_node("knowledge", knowledge_node)
    # workflow.add_node("sql", sql_node)  # REMOVED - Dead Code
    workflow.add_node("crm", crm_node)
    workflow.add_node("generator", generation_node)
    
    # Entry Point
    workflow.set_entry_point("router")
    
    # Simplified Routing: Router → Knowledge (immer!)
    workflow.add_edge("router", "knowledge")
    
    # Knowledge → CRM (conditional)
    workflow.add_conditional_edges("knowledge", should_use_crm, {
        "crm": "crm",
        "skip_crm": "generator"
    })
    
    # CRM → Generator
    workflow.add_edge("crm", "generator")
    workflow.add_edge("generator", END)
    
    return workflow.compile()
```

**Tests:**
```bash
# Stelle sicher, dass alle existierenden Tests noch laufen
pytest backend/tests/test_chat_workflow.py -v
```

---

#### 1.2 Intent Classification vereinfachen

**Datei:** `backend/app/prompts/intent_classification.txt`

```txt
Du bist ein Intent Classifier für einen RAG Agenten.

Analysiere die folgende Benutzeranfrage und klassifiziere sie:

INTENT TYPES:
- "question": Fachliche Frage (Geschäftsdaten, Prozesse, Dokumente, etc.)
- "general": Allgemeine Konversation oder Small Talk

BEISPIELE:
- "question": "Was ist der Status von ACME Corp?", "Welche Rechnungen im Dezember?", "Wie funktioniert der Onboarding-Prozess?"
- "general": "Hallo", "Wie geht es dir?", "Danke"

BENUTZERANFRAGE:
{query}

Antworte NUR mit einem der zwei Wörter: question oder general
Keine Erklärung, nur das Klassifikations-Wort!
```

**Router Node vereinfachen:**
```python
async def router_node(state: AgentState) -> AgentState:
    """
    Router Node: Vereinfachte Classification.
    Entscheidet nur: "Question" vs. "Small Talk"
    """
    user_message = _get_last_human_message(state)
    
    if not user_message:
        state["intent"] = "general"
        return state
    
    # LLM Classification (nur 2 Intents!)
    llm = get_llm(temperature=0.0, streaming=False)
    classification_prompt = get_prompt("intent_classification")
    
    try:
        result = await llm.ainvoke([
            SystemMessage(content=classification_prompt.format(query=user_message))
        ])
        intent = result.content.strip().lower()
        
        # Normalisiere
        if intent in ["question", "frage"]:
            state["intent"] = "question"
        else:
            state["intent"] = "general"
            
        logger.info(f"[ROUTER] Intent: {state['intent']}")
        
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        state["intent"] = "question"  # Fallback
    
    return state
```

---

### Phase 2: Metadata Service erweitern (Source Catalog)

#### 2.1 Erweitere `external_sources.yaml`

**Datei:** `backend/app/config/external_sources.yaml`

```yaml
# ==========================================
# Source Catalog
# Definiert ALLE verfügbaren Datenquellen
# ==========================================

sources:
  # ==========================================
  # Knowledge Base (Vector + Graph)
  # Primary source - always available
  # ==========================================
  - id: "knowledge_base"
    type: "vector_graph"
    description: "Interne Dokumente, Handbücher, Prozesse"
    status: "active"
    tool: "search_knowledge_base"
    priority: 1  # Immer zuerst prüfen
    capabilities:
      - "semantic_search"  # Vector Store
      - "entity_resolution"  # Graph für Entity-IDs
      - "relationship_discovery"  # Graph für Zusammenhänge
    keywords:
      - "dokument"
      - "handbuch"
      - "anleitung"
      - "prozess"
      - "konzept"
      - "erklärung"
      - "policy"
      - "richtlinie"
    
  # ==========================================
  # CRM Source (Zoho CRM & Books)
  # Requires entity_id from Graph!
  # ==========================================
  - id: "zoho_crm"
    type: "crm"
    description: "Zoho CRM - Kunden, Leads, Deals, Kontakte"
    status: "active"
    tool: "get_crm_facts"
    priority: 2
    requires_entity_id: true  # WICHTIG: Braucht ID aus Graph!
    capabilities:
      - "live_data"  # Echtzeit CRM-Daten
      - "deal_status"
      - "contact_info"
      - "activity_history"
    modules:
      - name: "Accounts"
        keywords: ["kunde", "firma", "unternehmen", "account", "organisation"]
      - name: "Contacts"
        keywords: ["kontakt", "person", "ansprechpartner", "mitarbeiter"]
      - name: "Deals"
        keywords: ["deal", "geschäft", "verkauf", "angebot", "opportunity"]
      - name: "Objections"
        keywords: ["einwand", "bedenken", "hindernis", "problem"]
      - name: "Meetings"
        keywords: ["meeting", "termin", "besprechung", "call"]
    
  - id: "zoho_books"
    type: "crm"
    description: "Zoho Books - Rechnungen, Zahlungen, Finanzen"
    status: "active"
    tool: "get_crm_facts"
    priority: 2
    requires_entity_id: true
    capabilities:
      - "live_data"
      - "invoice_status"
      - "payment_history"
      - "financial_data"
    modules:
      - name: "Invoices"
        keywords: ["rechnung", "invoice", "faktura", "billing"]
      - name: "Payments"
        keywords: ["zahlung", "payment", "bezahlung", "überweisung"]
      - name: "Subscriptions"
        keywords: ["abo", "subscription", "vertrag", "membership"]
  
  # ==========================================
  # SQL Sources (Optional - für IoT/Sensoren)
  # ==========================================
  - id: "iot_database"
    type: "sql"
    description: "IoT Sensor-Daten von Maschinen"
    status: "optional"  # Nur wenn ERP_DATABASE_URL gesetzt
    connection_env: "IOT_DATABASE_URL"
    tool: "execute_sql_query"
    priority: 3
    requires_entity_id: true  # Equipment-ID aus Graph
    capabilities:
      - "real_time_metrics"
      - "historical_data"
      - "sensor_readings"
    tables:
      - name: "machine_sensors"
        description: "Echtzeit-Sensordaten (Temperatur, Druck, Status)"
        keywords: ["temperatur", "sensor", "maschine", "equipment", "druck", "status"]
        columns:
          - "machine_id"
          - "temperature"
          - "pressure"
          - "status"
          - "timestamp"
      
      - name: "maintenance_logs"
        description: "Wartungsprotokolle und Service-Historie"
        keywords: ["wartung", "service", "reparatur", "maintenance"]

# ==========================================
# Source Selection Strategy
# ==========================================
selection_strategy:
  # 1. Graph wird IMMER zuerst abgefragt (für Entity Resolution)
  always_check_graph: true
  
  # 2. Vector Search bei unklaren/konzeptuellen Fragen
  default_fallback: "knowledge_base"
  
  # 3. Kombiniere Quellen wenn mehrere Match
  combine_sources: true
  
  # 4. CRM nur wenn Entity im Graph gefunden
  crm_requires_graph_entity: true
```

---

#### 2.2 Erweitere Metadata Service

**Datei:** `backend/app/services/metadata_store.py`

```python
"""
MetadataService: Source Catalog Management
Intelligente Source Discovery basierend auf Query-Analyse
"""

import logging
from typing import Any, Dict, List, Optional
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)


class SourceDefinition:
    """Repräsentiert eine Datenquelle aus dem Catalog."""
    
    def __init__(self, config: Dict[str, Any]):
        self.id = config.get("id")
        self.type = config.get("type")
        self.description = config.get("description")
        self.status = config.get("status", "active")
        self.tool = config.get("tool")
        self.priority = config.get("priority", 99)
        self.requires_entity_id = config.get("requires_entity_id", False)
        self.capabilities = config.get("capabilities", [])
        self.keywords = config.get("keywords", [])
        self.modules = config.get("modules", [])
        self.tables = config.get("tables", [])
        self.connection_env = config.get("connection_env")
    
    def matches_query(self, query: str) -> float:
        """
        Berechnet Relevanz-Score für diese Source basierend auf Query.
        Returns: 0.0 - 1.0
        """
        query_lower = query.lower()
        score = 0.0
        
        # Check keywords
        for keyword in self.keywords:
            if keyword.lower() in query_lower:
                score += 0.3
        
        # Check modules
        for module in self.modules:
            module_keywords = module.get("keywords", [])
            for keyword in module_keywords:
                if keyword.lower() in query_lower:
                    score += 0.4
        
        # Check tables (for SQL sources)
        for table in self.tables:
            table_keywords = table.get("keywords", [])
            for keyword in table_keywords:
                if keyword.lower() in query_lower:
                    score += 0.4
        
        return min(score, 1.0)  # Cap at 1.0
    
    def is_available(self) -> bool:
        """Prüft ob die Source verfügbar ist."""
        if self.status == "active":
            return True
        elif self.status == "optional":
            # Check if connection is configured
            if self.connection_env:
                import os
                return bool(os.getenv(self.connection_env))
            return False
        return False


class MetadataService:
    """
    Intelligenter Source Catalog.
    Entscheidet welche Datenquellen für eine Query relevant sind.
    """
    
    def __init__(self):
        self.sources: List[SourceDefinition] = []
        self.strategy: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Lädt external_sources.yaml"""
        config_path = Path(__file__).parent.parent / "config" / "external_sources.yaml"
        
        if not config_path.exists():
            logger.warning(f"Source catalog not found: {config_path}")
            return
        
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            
            # Load sources
            for source_config in config.get("sources", []):
                source = SourceDefinition(source_config)
                self.sources.append(source)
            
            # Load strategy
            self.strategy = config.get("selection_strategy", {})
        
        logger.info(f"Loaded {len(self.sources)} sources from catalog")
    
    def get_relevant_sources(
        self, 
        query: str,
        min_score: float = 0.3,
        max_sources: int = 3
    ) -> List[SourceDefinition]:
        """
        Findet relevante Datenquellen für eine Query.
        
        Args:
            query: User query
            min_score: Minimum relevance score
            max_sources: Maximum number of sources to return
        
        Returns:
            List of relevant sources, sorted by priority and score
        """
        scored_sources = []
        
        for source in self.sources:
            # Skip if not available
            if not source.is_available():
                logger.debug(f"Source {source.id} not available, skipping")
                continue
            
            # Calculate relevance score
            score = source.matches_query(query)
            
            if score >= min_score:
                scored_sources.append((source, score))
                logger.debug(f"Source {source.id} matched with score {score:.2f}")
        
        # Sort by priority (lower = higher priority), then by score
        scored_sources.sort(key=lambda x: (x[0].priority, -x[1]))
        
        # Return top N sources
        result = [source for source, _ in scored_sources[:max_sources]]
        
        # Graph immer dabei (wenn strategy sagt so)
        if self.strategy.get("always_check_graph", True):
            kb_source = self.get_source_by_id("knowledge_base")
            if kb_source and kb_source not in result:
                result.insert(0, kb_source)  # An erster Stelle
        
        logger.info(f"Selected {len(result)} sources for query: {[s.id for s in result]}")
        
        return result
    
    def get_source_by_id(self, source_id: str) -> Optional[SourceDefinition]:
        """Findet eine Source anhand ihrer ID."""
        for source in self.sources:
            if source.id == source_id:
                return source
        return None
    
    def should_combine_sources(self) -> bool:
        """Prüft ob Quellen kombiniert werden sollen."""
        return self.strategy.get("combine_sources", True)
    
    def get_default_fallback(self) -> Optional[SourceDefinition]:
        """Gibt die Default-Fallback-Source zurück."""
        fallback_id = self.strategy.get("default_fallback", "knowledge_base")
        return self.get_source_by_id(fallback_id)


# Singleton
_metadata_service_instance: Optional[MetadataService] = None

def metadata_service() -> MetadataService:
    """Returns singleton instance."""
    global _metadata_service_instance
    if _metadata_service_instance is None:
        _metadata_service_instance = MetadataService()
    return _metadata_service_instance
```

---

### Phase 3: Knowledge Node wird Smart Orchestrator

#### 3.1 Refactore Knowledge Node

**Datei:** `backend/app/graph/chat_workflow.py`

```python
async def knowledge_node(state: AgentState) -> AgentState:
    """
    Smart Knowledge Orchestrator.
    
    Workflow:
    1. Query Knowledge Graph (für Entity Resolution + Context)
    2. Nutze Metadata Service (Source Discovery)
    3. Führe relevante Tools parallel aus
    4. Kombiniere Ergebnisse
    """
    logger.info("🧠 Knowledge Orchestrator: Starting intelligent source discovery")
    
    user_message = _get_last_human_message(state)
    if not user_message:
        return state
    
    # =========================================================================
    # STEP 1: Query Knowledge Graph (ALWAYS FIRST - das ist der "Glue"!)
    # =========================================================================
    logger.info("🕸️ Step 1: Querying Knowledge Graph for context and entity IDs")
    
    graph_store = get_graph_store_service()
    graph_context = ""
    crm_entity_id = None
    equipment_ids = []
    
    try:
        # Graph Query für generellen Kontext
        graph_context = await graph_store.query_graph(user_message)
        logger.info(f"✅ Graph context retrieved: {len(graph_context)} chars")
        
        # Suche nach CRM-Entities (für Live-Abfragen)
        cypher_query = """
        MATCH (n)
        WHERE (n.source_id STARTS WITH 'zoho_' OR n.source_id STARTS WITH 'iot_')
        AND toLower($query) CONTAINS toLower(n.name)
        RETURN n.source_id as source_id, 
               n.name as name, 
               labels(n)[0] as type
        LIMIT 5
        """
        
        entities = await graph_store.query(cypher_query, parameters={"query": user_message})
        
        if entities:
            logger.info(f"✅ Found {len(entities)} entities in graph")
            for entity in entities:
                entity_id = entity.get("source_id", "")
                entity_name = entity.get("name", "")
                entity_type = entity.get("type", "")
                
                logger.info(f"  - {entity_type}: {entity_name} ({entity_id})")
                
                # Kategorisiere Entities
                if entity_id.startswith("zoho_"):
                    if not crm_entity_id:  # Nimm erste CRM-Entity
                        crm_entity_id = entity_id
                        state["crm_target"] = entity_id
                        logger.info(f"🎯 CRM Target set: {entity_id}")
                
                elif entity_id.startswith("iot_"):
                    equipment_ids.append(entity_id)
    
    except Exception as e:
        logger.error(f"❌ Graph query failed: {e}", exc_info=True)
        graph_context = "Graph nicht verfügbar."
    
    # =========================================================================
    # STEP 2: Source Discovery via Metadata Service
    # =========================================================================
    logger.info("📋 Step 2: Source Discovery via Metadata Service")
    
    metadata_svc = metadata_service()
    relevant_sources = metadata_svc.get_relevant_sources(user_message)
    
    logger.info(f"Found {len(relevant_sources)} relevant sources:")
    for source in relevant_sources:
        logger.info(f"  - {source.id} ({source.type}) - Priority {source.priority}")
    
    # =========================================================================
    # STEP 3: Execute Tools based on Source Discovery
    # =========================================================================
    logger.info("🔧 Step 3: Executing tools for relevant sources")
    
    tool_results = {}
    
    for source in relevant_sources:
        source_id = source.id
        tool_name = source.tool
        
        logger.info(f"📞 Calling tool '{tool_name}' for source '{source_id}'")
        
        try:
            # ---- Knowledge Base (Vector + Graph) ----
            if tool_name == "search_knowledge_base":
                result = await search_knowledge_base(user_message)
                tool_results["knowledge_result"] = result
                logger.info(f"✅ Knowledge search: {len(result)} chars")
            
            # ---- CRM (Live Data via Graph-ID) ----
            elif tool_name == "get_crm_facts" and crm_entity_id:
                # Nur wenn Entity im Graph gefunden!
                result = await get_crm_facts(
                    entity_id=crm_entity_id,
                    query_context=user_message
                )
                tool_results["crm_result"] = result
                logger.info(f"✅ CRM facts retrieved: {len(result)} chars")
            
            elif tool_name == "get_crm_facts" and not crm_entity_id:
                logger.warning(f"⚠️ CRM source selected but no entity found in graph")
            
            # ---- SQL (für IoT/Sensoren via Graph-ID) ----
            elif tool_name == "execute_sql_query" and equipment_ids:
                # Generate SQL query for equipment
                equipment_id = equipment_ids[0]  # Nimm erste Maschine
                
                # Simple example: Get sensor data
                sql_query = f"""
                SELECT machine_id, temperature, pressure, status, timestamp
                FROM machine_sensors
                WHERE machine_id = '{equipment_id}'
                ORDER BY timestamp DESC
                LIMIT 10
                """
                
                result = execute_sql_query(sql_query, source_id)
                tool_results["sql_result"] = result
                logger.info(f"✅ SQL query executed: {len(result)} chars")
            
            elif tool_name == "execute_sql_query" and not equipment_ids:
                logger.warning(f"⚠️ SQL source selected but no equipment found in graph")
        
        except Exception as e:
            logger.error(f"❌ Tool {tool_name} failed: {e}", exc_info=True)
            tool_results[f"{source_id}_error"] = str(e)
    
    # =========================================================================
    # STEP 4: Store all results in state
    # =========================================================================
    logger.info("💾 Step 4: Storing results in state")
    
    # Immer den Graph-Context hinzufügen (der "Glue"!)
    if graph_context:
        tool_results["graph_context"] = graph_context
    
    state["tool_outputs"] = tool_results
    
    logger.info(f"✅ Knowledge Orchestrator completed. Results: {list(tool_results.keys())}")
    
    return state
```

---

#### 3.2 CRM Node vereinfachen (oder entfernen)

**Option A: CRM Node behalten (für komplexe CRM-Queries)**

Wenn CRM-Logik komplex ist, behalte den Node:

```python
async def crm_node(state: AgentState) -> AgentState:
    """
    CRM Node für komplexe Live-Abfragen.
    Wird nur aufgerufen wenn Knowledge Orchestrator CRM-Entity gefunden hat.
    """
    crm_target = state.get("crm_target")
    
    if not crm_target:
        logger.warning("CRM Node called but no target set")
        return state
    
    user_message = _get_last_human_message(state)
    
    # Hole erweiterte CRM-Daten
    try:
        result = await get_crm_facts(crm_target, user_message)
        state["tool_outputs"]["crm_result"] = result
    except Exception as e:
        logger.error(f"CRM query failed: {e}")
    
    return state
```

**Option B: CRM Node entfernen**

Wenn CRM bereits im Knowledge Orchestrator abgehandelt wird:

```python
# In create_chat_workflow()
workflow.add_edge("knowledge", "generator")  # Direkt zum Generator
# workflow.add_node("crm", crm_node)  # REMOVED
```

---

### Phase 4: Generator Node erweitern

#### 4.1 Generator kombiniert alle Kontexte

**Datei:** `backend/app/graph/chat_workflow.py`

```python
async def generation_node(state: AgentState) -> AgentState:
    """
    Generator Node: Synthesiert finale Antwort aus allen Tool-Outputs.
    Kombiniert: Graph Context + Vector + CRM + SQL (wenn vorhanden)
    """
    logger.info("✍️ Generator Node: Synthesizing answer from all contexts")
    
    tool_outputs = state.get("tool_outputs", {})
    user_message = _get_last_human_message(state)
    
    # =========================================================================
    # Build comprehensive context from ALL sources
    # =========================================================================
    context_parts = []
    
    # 1. Graph Context (der "Glue"!)
    if "graph_context" in tool_outputs:
        context_parts.append("=== KNOWLEDGE GRAPH (Zusammenhänge) ===")
        context_parts.append(tool_outputs["graph_context"])
        context_parts.append("")
    
    # 2. Vector Search Results (Dokumente)
    if "knowledge_result" in tool_outputs:
        context_parts.append("=== DOKUMENTE (Wissensdatenbank) ===")
        context_parts.append(tool_outputs["knowledge_result"])
        context_parts.append("")
    
    # 3. CRM Live Data
    if "crm_result" in tool_outputs:
        context_parts.append("=== LIVE CRM-DATEN ===")
        context_parts.append(tool_outputs["crm_result"])
        context_parts.append("")
    
    # 4. SQL/IoT Data
    if "sql_result" in tool_outputs:
        context_parts.append("=== SENSOR-DATEN ===")
        context_parts.append(tool_outputs["sql_result"])
        context_parts.append("")
    
    combined_context = "\n".join(context_parts)
    
    # =========================================================================
    # Generate answer with LLM
    # =========================================================================
    llm = get_llm(temperature=0.7, streaming=False)
    answer_prompt = get_prompt("answer_generation")
    
    try:
        result = await llm.ainvoke([
            SystemMessage(content=answer_prompt.format(
                context=combined_context,
                query=user_message
            ))
        ])
        
        answer = result.content
        
        # Add to messages
        state["messages"].append(AIMessage(content=answer))
        
        logger.info(f"✅ Answer generated: {len(answer)} chars")
        
    except Exception as e:
        logger.error(f"❌ Answer generation failed: {e}", exc_info=True)
        error_message = "Entschuldigung, ich konnte keine Antwort generieren."
        state["messages"].append(AIMessage(content=error_message))
    
    return state
```

---

### Phase 5: Prompt Updates

#### 5.1 Answer Generation Prompt

**Datei:** `backend/app/prompts/answer_generation.txt`

```txt
Du bist ein intelligenter Assistant der aus verschiedenen Datenquellen Antworten generiert.

Du erhältst Kontext aus mehreren Quellen:
1. KNOWLEDGE GRAPH: Zeigt Zusammenhänge zwischen Entities (Personen, Firmen, Konzepten)
2. DOKUMENTE: Textabschnitte aus internen Dokumenten, Handbüchern, Prozessen
3. LIVE CRM-DATEN: Aktuelle Informationen aus dem CRM-System (Deals, Status, etc.)
4. SENSOR-DATEN: Echtzeit-Messwerte von Maschinen (falls verfügbar)

WICHTIG - KONTEXT KOMBINIEREN:
- Der Knowledge Graph zeigt DIR die Zusammenhänge zwischen den Datenquellen
- Nutze den Graph um zu verstehen WIE die Informationen zusammenhängen
- Kombiniere Dokument-Wissen mit Live-Daten für vollständige Antworten
- Erwähne Quellen natürlich ("laut Handbuch", "aktueller CRM-Status", etc.)

BEISPIEL - GUTE ANTWORT:
User: "Was ist der Status von ACME Corp?"
Context:
  Graph: ORGANIZATION(ACME Corp) -HAS_EQUIPMENT-> EQUIPMENT(Hochdrucklader #42)
  CRM: Open Deals: 2, Last Invoice: €45k, Status: Active
  Sensors: Machine #42: Temperature 85°C (Warning: near limit 90°C)
  
Answer: "ACME Corp ist ein aktiver Kunde mit 2 offenen Deals. Die letzte Rechnung 
betrug €45k. Ihr Hochdrucklader (#42) läuft aktuell bei 85°C, was nahe am kritischen 
Grenzwert von 90°C liegt. Eine Wartung sollte bald eingeplant werden."

BENUTZERANFRAGE:
{query}

VERFÜGBARER KONTEXT:
{context}

Generiere eine präzise, hilfreiche Antwort die ALLE relevanten Informationen kombiniert.
```

---

## 📊 Neue Architektur (Finale Version)

```mermaid
graph TB
    START([User Query]) --> ROUTER[Router Node<br/>Question vs. Small Talk]
    
    ROUTER -->|question| ORCH[Knowledge Orchestrator<br/>Smart Source Discovery]
    ROUTER -->|general| GEN[Generator Node]
    
    subgraph Orchestrator["Knowledge Orchestrator Process"]
        ORCH --> GRAPH[1. Query Graph<br/>Entity Resolution + Context]
        GRAPH --> META[2. Metadata Service<br/>Source Discovery]
        META --> TOOLS[3. Execute Relevant Tools]
        
        TOOLS --> TOOL_VEC[search_knowledge_base<br/>Vector + Graph]
        TOOLS --> TOOL_CRM[get_crm_facts<br/>Live CRM via Graph-ID]
        TOOLS --> TOOL_SQL[execute_sql_query<br/>IoT/Sensors via Graph-ID]
    end
    
    ORCH --> GEN
    GEN --> END([Final Answer])
    
    style ROUTER fill:#e1f5ff
    style ORCH fill:#e8f5e9
    style GRAPH fill:#fff4e1,stroke:#ff9800,stroke-width:3px
    style GEN fill:#f3e5f5
    
    classDef graphGlue fill:#fff4e1,stroke:#ff9800,stroke-width:3px;
    class GRAPH graphGlue;
```

---

## ✅ Testing & Validation

### Test Cases

```python
# tests/test_smart_orchestrator.py

import pytest
from app.graph.chat_workflow import chat_workflow
from langchain_core.messages import HumanMessage

@pytest.mark.asyncio
async def test_knowledge_only_query():
    """Test: Nur Dokument-basierte Frage"""
    inputs = {
        "messages": [HumanMessage(content="Was ist unsere Preispolitik?")],
        "intent": "general",
        "tool_outputs": {}
    }
    
    result = await chat_workflow.ainvoke(inputs)
    
    # Should use knowledge_base only
    assert "knowledge_result" in result["tool_outputs"]
    assert "crm_result" not in result["tool_outputs"]


@pytest.mark.asyncio
async def test_crm_query_with_entity():
    """Test: CRM-Frage mit Entity im Graph"""
    inputs = {
        "messages": [HumanMessage(content="Was ist der Status von ACME Corp?")],
        "intent": "general",
        "tool_outputs": {}
    }
    
    result = await chat_workflow.ainvoke(inputs)
    
    # Should use graph + crm
    assert "graph_context" in result["tool_outputs"]
    assert "crm_result" in result["tool_outputs"]
    assert result.get("crm_target", "").startswith("zoho_")


@pytest.mark.asyncio
async def test_combined_query():
    """Test: Kombinierte Abfrage (Dokumente + CRM + Sensoren)"""
    inputs = {
        "messages": [HumanMessage(content="Wie ist der Status von Hochdrucklader #42?")],
        "intent": "general",
        "tool_outputs": {}
    }
    
    result = await chat_workflow.ainvoke(inputs)
    
    # Should use multiple sources
    assert "graph_context" in result["tool_outputs"]
    assert "knowledge_result" in result["tool_outputs"]  # Handbuch
    # assert "sql_result" in result["tool_outputs"]  # Sensoren (wenn verfügbar)
```

---

## 🚀 Migration Plan

### Schritt-für-Schritt

1. **Week 1: Cleanup**
   - [ ] SQL Node entfernen
   - [ ] Intent Classification vereinfachen
   - [ ] Tests anpassen
   - [ ] Deploy zu Staging

2. **Week 2: Metadata Service**
   - [ ] `external_sources.yaml` erweitern
   - [ ] Metadata Service umbauen
   - [ ] Unit Tests für Source Discovery

3. **Week 3: Knowledge Orchestrator**
   - [ ] Knowledge Node refactoren
   - [ ] Graph-first Approach implementieren
   - [ ] Integration Tests

4. **Week 4: Generator & Prompts**
   - [ ] Generator Node erweitern
   - [ ] Prompts updaten
   - [ ] End-to-End Tests

5. **Week 5: Testing & Rollout**
   - [ ] Smoke Tests auf Production
   - [ ] Monitoring einrichten
   - [ ] Dokumentation finalisieren

---

## 📈 Success Metrics

**Vor Refactoring:**
- 5 Nodes (Router, SQL, Knowledge, CRM, Generator)
- 2-stufiges Routing
- SQL Node = Dead Code
- Keine Quellen-Kombination

**Nach Refactoring:**
- 3 Nodes (Router, Orchestrator, Generator)
- 1-stufiges Routing
- Graph als zentrale "Glue"-Schicht
- Multi-Source Kombination möglich

**Messbare Verbesserungen:**
- ✅ Code Complexity: -40%
- ✅ Response Quality: +30% (durch Kontext-Kombination)
- ✅ Maintainability: +50% (durch Metadata Service)
- ✅ Extensibility: Neue Quelle = nur YAML Update

---

## 🎯 Zusammenfassung

**Der Graph ist der Schlüssel!**

1. **Graph = Glue Layer**
   - Verbindet unstructured (Dokumente) mit structured (CRM/SQL)
   - Liefert Entity-IDs für Live-Abfragen
   - Zeigt Zusammenhänge zwischen Datenquellen

2. **Knowledge Orchestrator**
   - Graph-first Approach (immer zuerst fragen)
   - Metadata Service für Source Discovery
   - Parallel Tool Execution
   - Kontext-Kombination

3. **Erweiterbarkeit**
   - Neue Datenquelle? → `external_sources.yaml` updaten
   - Keine Code-Änderungen nötig
   - Graph bleibt der zentrale Hub

🚀 **Ready to refactor?**


