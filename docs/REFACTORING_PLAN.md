# Refactoring Plan: ingestion.py & Zoho Integration

**Datum:** 2026-01-09  
**Status:** 🔄 In Arbeit  
**Priorität:** HIGH

---

## 🎯 Ziele

1. **Code-Qualität verbessern** - Trennung von Concerns, bessere Lesbarkeit
2. **Fehlerbehandlung robuster machen** - Detaillierte Error-Tracking
3. **Performance optimieren** - Batch-Processing verbessern
4. **Wartbarkeit erhöhen** - Modularer, testbarer Code

---

## 📊 Aktuelle Probleme

### 1. **Monolithische CRM Sync Funktion** (ingestion.py:311-658)
**Problem:** 347 Zeilen in einer Funktion mit mehreren Verantwortlichkeiten

**Betroffene Bereiche:**
- Daten-Fetching (Provider-Aufruf)
- Property-Sanitization (JSON-Handling)
- Node-Creation (Batch UNWIND)
- Relationship-Creation (Batch UNWIND)
- Error-Tracking & Reporting
- Timestamp-Management

**Impact:** 
- Schwer zu testen
- Schwer zu debuggen
- Schwer zu erweitern

---

### 2. **Inline Property Sanitization** (ingestion.py:385-420)
**Problem:** 35 Zeilen Helper-Funktion innerhalb der Sync-Funktion

```python
def _sanitize_properties(props: dict) -> dict:
    """Nested function - should be extracted"""
    sanitized = {}
    for key, value in props.items():
        if value is None:
            continue
        elif isinstance(value, dict):
            # Zoho lookup field handling
            if "id" in value:
                sanitized[f"{key}_id"] = str(value["id"])
                if "name" in value:
                    sanitized[f"{key}_name"] = str(value["name"])
            else:
                sanitized[key] = json.dumps(value)
        # ... more logic
    return sanitized
```

**Lösung:** Extrahieren in `app/services/crm_sync_service.py`

---

### 3. **Komplexe Relationship-Gruppierung** (ingestion.py:534-598)
**Problem:** Verschachtelte Logik für Relationship-Batching

```python
relations_by_key = {}
for rel in all_relations:
    key = (rel["edge_type"], rel.get("target_label", "CRMEntity"), rel["direction"])
    if key not in relations_by_key:
        relations_by_key[key] = []
    relations_by_key[key].append(rel)

for (edge_type, target_label, direction), relations in relations_by_key.items():
    # Complex Cypher generation
    if direction == "OUTGOING":
        cypher_query = f"""..."""
    elif direction == "INCOMING":
        cypher_query = f"""..."""
```

**Lösung:** Extrahieren in `RelationshipBatchProcessor` Klasse

---

### 4. **Fehlendes Error-Recovery** 
**Problem:** Partial Failures werden nicht gut gehandhabt

**Szenarien:**
- Node-Batch schlägt fehl → Alle Nodes in Batch verloren
- Relationship-Batch schlägt fehl → Keine Retry-Logik
- Provider-Fehler → Kein Fallback

**Lösung:** 
- Einzelne Entity-Fehler tracken
- Batch-Retry mit kleineren Batches
- Detailed Error-Reporting

---

### 5. **Keine Incremental Sync Optimierung**
**Problem:** Jeder Sync ist ein Full Sync

**Aktuell:**
```python
last_sync_time = await graph_store.get_last_sync_time("crm_sync")
skeleton_data = await provider.fetch_skeleton_data(
    entity_types=request.entity_types,
    last_sync_time=last_sync_time  # ← Wird übergeben aber nicht optimal genutzt
)
```

**Verbesserung:**
- Bessere Modified_Time Filterung
- Delta-Detection auf Node-Ebene
- Relationship-Diff statt Full Replace

---

## 🏗️ Refactoring-Architektur

### Neue Struktur

```
backend/app/services/
├── crm_sync/
│   ├── __init__.py
│   ├── sync_orchestrator.py      # Hauptlogik (orchestriert)
│   ├── property_sanitizer.py     # Property-Handling
│   ├── node_batch_processor.py   # Node-Creation
│   ├── relationship_processor.py # Relationship-Creation
│   ├── error_tracker.py          # Error-Tracking & Reporting
│   └── sync_state_manager.py     # Timestamp & State Management
```

### Klassen-Design

#### 1. `CRMSyncOrchestrator`
```python
class CRMSyncOrchestrator:
    """
    Orchestrates CRM sync workflow.
    
    Responsibilities:
    - Coordinate sync phases
    - Manage dependencies between processors
    - Aggregate results & errors
    """
    
    def __init__(
        self,
        graph_store: GraphStoreService,
        property_sanitizer: PropertySanitizer,
        node_processor: NodeBatchProcessor,
        relationship_processor: RelationshipProcessor,
        error_tracker: ErrorTracker,
        state_manager: SyncStateManager
    ):
        ...
    
    async def sync(
        self,
        provider: CRMProvider,
        entity_types: Optional[List[str]] = None
    ) -> CRMSyncResult:
        """Main sync workflow"""
        # 1. Get last sync time
        # 2. Fetch skeleton data
        # 3. Process nodes
        # 4. Process relationships
        # 5. Update sync time
        # 6. Return results
```

#### 2. `PropertySanitizer`
```python
class PropertySanitizer:
    """
    Sanitizes CRM properties for Neo4j storage.
    
    Handles:
    - Lookup field flattening (id + name)
    - JSON serialization for complex types
    - Type validation
    """
    
    def sanitize(self, props: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize properties for Neo4j"""
        
    def _handle_lookup_field(self, key: str, value: dict) -> Dict[str, str]:
        """Extract id and name from lookup field"""
        
    def _serialize_complex_type(self, value: Any) -> str:
        """Serialize dicts/lists to JSON"""
```

#### 3. `NodeBatchProcessor`
```python
class NodeBatchProcessor:
    """
    Processes node creation in batches.
    
    Features:
    - Batch UNWIND queries
    - Label sanitization
    - Multi-label support (CRMEntity)
    - Error recovery with smaller batches
    """
    
    async def process_nodes(
        self,
        entities_by_label: Dict[str, List[Dict]],
        provider_name: str
    ) -> NodeProcessingResult:
        """Process all nodes grouped by label"""
        
    async def _process_label_batch(
        self,
        label: str,
        entities: List[Dict],
        provider_name: str
    ) -> BatchResult:
        """Process single label batch with retry logic"""
```

#### 4. `RelationshipProcessor`
```python
class RelationshipProcessor:
    """
    Processes relationship creation in batches.
    
    Features:
    - Relationship grouping by (edge_type, target_label, direction)
    - Dynamic Cypher generation
    - MATCH-based creation (no orphans)
    - Error recovery
    """
    
    async def process_relationships(
        self,
        relations: List[Dict]
    ) -> RelationshipProcessingResult:
        """Process all relationships"""
        
    def _group_relations(
        self,
        relations: List[Dict]
    ) -> Dict[Tuple[str, str, str], List[Dict]]:
        """Group relations by key"""
        
    def _build_cypher_query(
        self,
        edge_type: str,
        target_label: str,
        direction: str
    ) -> str:
        """Generate Cypher for relationship batch"""
```

#### 5. `ErrorTracker`
```python
class ErrorTracker:
    """
    Tracks errors during sync with detailed context.
    
    Features:
    - Entity-level error tracking
    - Batch-level error tracking
    - Error categorization (node vs relationship)
    - Detailed error reporting
    """
    
    def track_entity_error(
        self,
        entity_id: str,
        label: str,
        error: Exception,
        context: Dict[str, Any]
    ):
        """Track individual entity error"""
        
    def track_batch_error(
        self,
        batch_type: str,
        batch_size: int,
        error: Exception
    ):
        """Track batch processing error"""
        
    def get_summary(self) -> ErrorSummary:
        """Get error summary for response"""
```

#### 6. `SyncStateManager`
```python
class SyncStateManager:
    """
    Manages sync state and timestamps.
    
    Features:
    - Last sync time tracking
    - Incremental sync support
    - Sync statistics
    """
    
    async def get_last_sync_time(self, sync_type: str) -> Optional[datetime]:
        """Get last successful sync timestamp"""
        
    async def update_sync_time(self, sync_type: str, timestamp: datetime):
        """Update sync timestamp"""
        
    async def get_sync_stats(self) -> SyncStats:
        """Get sync statistics"""
```

---

## 📋 Refactoring-Schritte

### Phase 1: Extraction (Keine Funktionsänderung)
**Ziel:** Code extrahieren ohne Verhalten zu ändern

1. ✅ **Dokumentation aufräumen** (erledigt)
2. ⏳ **PropertySanitizer extrahieren**
   - Neue Datei: `app/services/crm_sync/property_sanitizer.py`
   - Tests schreiben
   - In ingestion.py integrieren
3. ⏳ **ErrorTracker extrahieren**
   - Neue Datei: `app/services/crm_sync/error_tracker.py`
   - Tests schreiben
4. ⏳ **NodeBatchProcessor extrahieren**
   - Neue Datei: `app/services/crm_sync/node_batch_processor.py`
   - Tests schreiben
5. ⏳ **RelationshipProcessor extrahieren**
   - Neue Datei: `app/services/crm_sync/relationship_processor.py`
   - Tests schreiben

### Phase 2: Orchestration
**Ziel:** Hauptlogik vereinfachen

6. ⏳ **CRMSyncOrchestrator erstellen**
   - Neue Datei: `app/services/crm_sync/sync_orchestrator.py`
   - Alle Prozessoren integrieren
7. ⏳ **ingestion.py refactoren**
   - sync_crm_entities() vereinfachen
   - Orchestrator nutzen
   - Tests anpassen

### Phase 3: Optimization
**Ziel:** Performance & Robustheit verbessern

8. ⏳ **Batch-Retry-Logik**
   - Bei Batch-Fehler: Retry mit kleineren Batches
   - Exponential Backoff
9. ⏳ **Incremental Sync optimieren**
   - Delta-Detection verbessern
   - Relationship-Diff implementieren
10. ⏳ **Monitoring & Metrics**
    - Sync-Dauer tracken
    - Error-Rates tracken
    - LangSmith Integration

---

## 🧪 Testing-Strategie

### Unit Tests
```python
# test_property_sanitizer.py
def test_sanitize_lookup_field():
    sanitizer = PropertySanitizer()
    props = {"Owner": {"id": "123", "name": "John"}}
    result = sanitizer.sanitize(props)
    assert result["owner_id"] == "123"
    assert result["owner_name"] == "John"

# test_node_batch_processor.py
async def test_process_nodes_success():
    processor = NodeBatchProcessor(graph_store)
    entities = {"Lead": [{"source_id": "123", "properties": {...}}]}
    result = await processor.process_nodes(entities, "zoho")
    assert result.created == 1
    assert result.errors == []
```

### Integration Tests
```python
# test_crm_sync_integration.py
async def test_full_sync_workflow():
    orchestrator = CRMSyncOrchestrator(...)
    result = await orchestrator.sync(provider, entity_types=["Leads"])
    assert result.status == "success"
    assert result.entities_synced > 0
```

---

## 📊 Erfolgs-Metriken

### Code-Qualität
- ✅ Funktionen < 50 Zeilen
- ✅ Klassen mit Single Responsibility
- ✅ Test Coverage > 80%
- ✅ Keine verschachtelten Funktionen

### Performance
- ✅ Sync-Zeit < 60 Sekunden (Full Sync)
- ✅ Incremental Sync < 10 Sekunden
- ✅ Error-Recovery ohne Datenverlust

### Wartbarkeit
- ✅ Neue Entity-Types in < 10 Minuten hinzufügbar
- ✅ Bugs in < 30 Minuten lokalisierbar
- ✅ Neue Features in < 2 Stunden implementierbar

---

## 🚀 Nächste Schritte

1. **PropertySanitizer extrahieren** (1-2 Stunden)
2. **Tests schreiben** (1 Stunde)
3. **Integration in ingestion.py** (30 Minuten)
4. **Deployment & Validation** (30 Minuten)

**Dann:** Weiter mit ErrorTracker und NodeBatchProcessor

---

**Status:** 📝 Plan erstellt, bereit für Umsetzung  
**Nächster Schritt:** PropertySanitizer extrahieren

