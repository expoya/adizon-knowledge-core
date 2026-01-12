# Phase 1 Cleanup - SQL Node Entfernt

> **Datum:** 2026-01-10  
> **Phase:** Refactoring Phase 1  
> **Status:** ✅ Abgeschlossen

---

## 🎯 Ziel

Vereinfachung der Routing-Logik durch Entfernen von Dead Code (SQL Node) und Vorbereitung für Smart Orchestrator Architecture.

---

## ✅ Durchgeführte Änderungen

### 1. **SQL Node entfernt**

**Dateien:**
- `backend/app/graph/chat_workflow.py`

**Änderungen:**
```python
# VORHER: 5 Nodes
workflow.add_node("router", router_node)
workflow.add_node("sql", sql_node)  # ← ENTFERNT
workflow.add_node("knowledge", knowledge_node)
workflow.add_node("crm", crm_node)
workflow.add_node("generator", generation_node)

# NACHHER: 4 Nodes
workflow.add_node("router", router_node)
workflow.add_node("knowledge", knowledge_node)
workflow.add_node("crm", crm_node)
workflow.add_node("generator", generation_node)
```

**Begründung:**
- SQL Node war deaktiviert (`external_sources.yaml` leer)
- Intent Classification Prompt sagte "SQL ist DEAKTIVIERT"
- Dead Code reduziert Komplexität

---

### 2. **AgentState vereinfacht**

**Datei:** `backend/app/graph/chat_workflow.py`

```python
# VORHER
class AgentState(TypedDict):
    messages: List[AnyMessage]
    intent: str  # "general", "sql", "knowledge", "hybrid", "crm"
    sql_context: Dict[str, Any]  # ← ENTFERNT
    crm_target: str
    tool_outputs: Dict[str, str]

# NACHHER
class AgentState(TypedDict):
    messages: List[AnyMessage]
    intent: str  # "question", "general"
    crm_target: str
    tool_outputs: Dict[str, str]
```

---

### 3. **Intent Classification vereinfacht**

**Datei:** `backend/app/prompts/intent_classification.txt`

**VORHER: 3 Intents**
- "sql" (DEAKTIVIERT)
- "knowledge"
- "general"

**NACHHER: 2 Intents**
- "question" - Fachliche Fragen
- "general" - Small Talk

**Beispiele:**
```
"Was ist der Status von Firma X?" → "question"
"Welche Rechnungen im Dezember?" → "question"
"Hallo" → "general"
"Danke" → "general"
```

---

### 4. **Router Node vereinfacht**

**Datei:** `backend/app/graph/chat_workflow.py`

**Entfernt:**
- ❌ SQL Intent Detection
- ❌ Metadata Service Check für SQL-Tabellen
- ❌ sql_context Populierung

**Behalten:**
- ✅ LLM Intent Classification (2 Intents)
- ✅ CRM Entity Detection im Graph
- ✅ crm_target Setzen

**Code:**
```python
async def router_node(state: AgentState) -> AgentState:
    """
    Vereinfachte Intent Classification.
    - "question" → Knowledge Orchestrator
    - "general" → Generator (Small Talk)
    """
    # LLM Classification
    intent = classify(user_message)  # → "question" oder "general"
    
    # Bei Fragen: Optional nach CRM-Entities suchen
    if intent == "question":
        entity_id = find_crm_entity_in_graph(user_message)
        if entity_id:
            state["crm_target"] = entity_id
    
    return state
```

---

### 5. **Routing-Funktionen vereinfacht**

**Datei:** `backend/app/graph/chat_workflow.py`

**Entfernt:**
```python
def should_use_sql(state):  # ← ENTFERNT
    return "sql" if intent == "sql" else "skip_sql"
```

**Vereinfacht:**
```python
# VORHER
def should_use_knowledge(state):
    intent = state.get("intent", "")
    return "knowledge" if intent in ["knowledge", "hybrid", "general"] else "skip_knowledge"

# NACHHER
def should_use_knowledge(state):
    intent = state.get("intent", "question")
    return "knowledge" if intent == "question" else "skip_knowledge"
```

---

### 6. **Workflow Konstruktion vereinfacht**

**Datei:** `backend/app/graph/chat_workflow.py`

```python
# VORHER: Komplexes 2-stufiges Routing
Router → (should_use_sql)
  ├─ SQL → Generator
  └─ Knowledge → (should_use_crm)
       ├─ CRM → Generator
       └─ Generator

# NACHHER: Simples 1-stufiges Routing
Router → (should_use_knowledge)
  ├─ Knowledge → (should_use_crm)
  │    ├─ CRM → Generator
  │    └─ Generator
  └─ Generator (bei Small Talk)
```

---

### 7. **API Endpoint angepasst**

**Datei:** `backend/app/api/endpoints/chat.py`

```python
# VORHER
inputs = {
    "messages": messages,
    "intent": "general",
    "sql_context": {},  # ← ENTFERNT
    "tool_outputs": {},
}

# NACHHER
inputs = {
    "messages": messages,
    "intent": "general",
    "crm_target": "",
    "tool_outputs": {},
}
```

---

### 8. **Imports bereinigt**

**Datei:** `backend/app/graph/chat_workflow.py`

**Entfernt:**
```python
from app.services.metadata_store import metadata_service  # ← ENTFERNT (noch nicht gebraucht)
from app.tools.sql import execute_sql_query, get_sql_schema  # ← ENTFERNT
import json  # ← ENTFERNT
import re  # ← ENTFERNT
from typing import Any, Dict  # ← ENTFERNT (nicht mehr gebraucht)
```

**Behalten:**
```python
from app.tools.knowledge import search_knowledge_base
from app.tools.crm import get_crm_facts
from app.services.graph_store import get_graph_store_service
```

---

## 📊 Metriken

| Metrik | Vorher | Nachher | Änderung |
|--------|--------|---------|----------|
| **Nodes** | 5 | 4 | -20% |
| **Intents** | 3 | 2 | -33% |
| **Routing-Funktionen** | 3 | 2 | -33% |
| **State Fields** | 5 | 4 | -20% |
| **Code Lines** | ~530 | ~350 | -34% |
| **Conditional Edges** | 2 | 2 | 0% |

---

## 🧪 Testing

### Manuelle Tests

```bash
# Test 1: Fachliche Frage
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Was ist unsere Preispolitik?"}'

# Erwartet: intent="question" → Knowledge Node

# Test 2: Small Talk
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hallo"}'

# Erwartet: intent="general" → Direkt Generator

# Test 3: CRM-Frage mit Entity
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Was ist der Status von ACME Corp?"}'

# Erwartet: intent="question" + crm_target="zoho_xxx" → Knowledge → CRM → Generator
```

---

## 🔄 Migration Notes

**Breaking Changes:**
- ❌ SQL Intent wird nicht mehr unterstützt
- ❌ sql_context existiert nicht mehr im State

**Kompatibilität:**
- ✅ Alle Knowledge-Queries funktionieren weiterhin
- ✅ CRM-Queries funktionieren weiterhin
- ✅ API bleibt gleich (keine Breaking Changes für Frontend)

**Nächste Schritte:**
- 📋 Phase 2: Metadata Service erweitern (Source Catalog)
- 🧠 Phase 3: Knowledge Node wird Smart Orchestrator
- 🎨 Phase 4: Generator kombiniert Multi-Source Contexts

---

## 📝 Dokumentation Updates

**Aktualisierte Dateien:**
- ✅ `docs/ROUTING_LOGIC.md` - Hinweis auf Phase 1
- ✅ `docs/changelogs/2026-01-10_phase1-cleanup.md` - Dieses Dokument
- ✅ `backend/app/prompts/intent_classification.txt` - Neue Intents

**Noch zu aktualisieren:**
- ⏳ `docs/AGENTIC_RAG.md` - Mermaid Charts anpassen
- ⏳ `docs/ARCHITECTURE.md` - Workflow Diagramme anpassen

---

## ✅ Phase 1 Status: ABGESCHLOSSEN

**Datum:** 2026-01-10  
**Dauer:** ~1 Stunde  
**Nächste Phase:** Phase 2 - Metadata Service erweitern


