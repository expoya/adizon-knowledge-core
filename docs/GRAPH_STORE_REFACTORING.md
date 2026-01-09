# 🔄 Graph Store Refactoring Plan

**Datum:** 2026-01-09  
**Status:** 🔄 In Arbeit  
**Priorität:** HIGH

---

## 🎯 Problem

`graph_store.py` ist ein **693 Zeilen Monolith** mit zu vielen Verantwortlichkeiten:

### Aktuelle Verantwortlichkeiten (8+):
1. ✅ **Driver-Management** - Neo4j Connection
2. ✅ **Index-Management** - Performance-kritische Indexes
3. ✅ **Node-Operations** - Create, Read, Delete
4. ✅ **Relationship-Operations** - Create, Query
5. ✅ **Document-Graph** - add_graph_documents (Entities + Relations)
6. ✅ **Query-Operations** - Cypher Queries, Graph Search
7. ✅ **Summary** - Graph Statistics
8. ✅ **Sync-Metadata** - Timestamp-Management
9. ✅ **Thread-Pool** - Async/Sync Bridge

**Problem:** Zu viele Concerns, schwer zu testen, schwer zu erweitern

---

## 🏗️ Neue Architektur

### Modul-Struktur

```
backend/app/services/graph_operations/
├── __init__.py                  # Public API
├── index_manager.py             # Index-Verwaltung (~100 Zeilen)
├── node_operations.py           # Node CRUD (~150 Zeilen)
├── relationship_operations.py   # Relationship CRUD (~100 Zeilen)
├── query_service.py             # Query & Search (~200 Zeilen)
├── sync_metadata.py             # Sync Timestamps (~80 Zeilen)
└── graph_store_facade.py        # Facade/Orchestrator (~150 Zeilen)
```

**Total:** ~780 Zeilen gut strukturierter Code  
**Statt:** 693 Zeilen monolithischer Code

---

## 📋 Klassen-Design

### 1. `GraphIndexManager`
**Verantwortung:** Index-Verwaltung für Performance

**Methods:**
- `ensure_indexes()` - Create performance-critical indexes
- `create_index(label, property)` - Create single index
- `list_indexes()` - List all indexes
- `drop_index(name)` - Drop index

**Lines:** ~100

---

### 2. `GraphNodeOperations`
**Verantwortung:** Node CRUD Operations

**Methods:**
- `create_node(label, properties)` - Create single node
- `merge_node(label, properties, merge_keys)` - Merge node (avoid duplicates)
- `get_node(label, filters)` - Get node by filters
- `update_node(label, filters, properties)` - Update node
- `delete_node(label, filters)` - Delete node
- `delete_by_document_id(document_id)` - Delete document nodes
- `delete_by_filename(filename)` - Delete filename nodes

**Lines:** ~150

---

### 3. `GraphRelationshipOperations`
**Verantwortung:** Relationship CRUD Operations

**Methods:**
- `create_relationship(from_node, to_node, rel_type, properties)` - Create relationship
- `merge_relationship(from_node, to_node, rel_type, properties)` - Merge relationship
- `get_relationships(filters)` - Get relationships
- `delete_relationship(filters)` - Delete relationship

**Lines:** ~100

---

### 4. `GraphQueryService`
**Verantwortung:** Query & Search Operations

**Methods:**
- `execute_query(cypher, parameters)` - Execute raw Cypher
- `query_graph(question)` - Natural language → Graph query
- `get_summary()` - Graph statistics
- `search_nodes(keywords)` - Keyword-based search
- `get_related(node_id, depth)` - Get related nodes

**Lines:** ~200

---

### 5. `GraphSyncMetadata`
**Verantwortung:** Sync Timestamp Management

**Methods:**
- `get_last_sync_time(sync_key)` - Get last sync timestamp
- `set_last_sync_time(timestamp, sync_key)` - Set sync timestamp
- `get_sync_stats(sync_key)` - Get sync statistics
- `clear_sync_metadata(sync_key)` - Clear sync metadata

**Lines:** ~80

---

### 6. `GraphStoreService` (Facade)
**Verantwortung:** Unified API / Orchestration

**Delegates to:**
- `index_manager` - Index operations
- `node_ops` - Node operations
- `rel_ops` - Relationship operations
- `query_service` - Query operations
- `sync_metadata` - Sync operations

**Methods:**
- All public methods from sub-services (delegates)
- `add_graph_documents()` - High-level document graph creation
- `close()` - Cleanup

**Lines:** ~150

---

## 🔄 Migration Strategy

### Phase 1: Extraction (No Breaking Changes)
1. ✅ Create module structure
2. ⏳ Extract `GraphIndexManager`
3. ⏳ Extract `GraphNodeOperations`
4. ⏳ Extract `GraphRelationshipOperations`
5. ⏳ Extract `GraphQueryService`
6. ⏳ Extract `GraphSyncMetadata`

### Phase 2: Facade
7. ⏳ Create `GraphStoreService` facade
8. ⏳ Update imports (backward compatible)
9. ⏳ Tests anpassen

### Phase 3: Cleanup
10. ⏳ Remove old monolithic methods
11. ⏳ Update documentation
12. ⏳ Deploy & validate

---

## ✅ Success Criteria

### Code-Qualität
- ✅ Klassen < 200 Zeilen
- ✅ Single Responsibility per Klasse
- ✅ Test Coverage > 80%
- ✅ Keine verschachtelten Funktionen

### API Compatibility
- ✅ Keine Breaking Changes
- ✅ Alle bestehenden Tests passed
- ✅ Backward compatible imports

### Performance
- ✅ Keine Regression
- ✅ Index-Creation beim Start
- ✅ Async/Sync Bridge beibehalten

---

## 📝 Implementation Steps

1. **GraphIndexManager** (30 Min)
2. **GraphSyncMetadata** (20 Min)
3. **GraphNodeOperations** (45 Min)
4. **GraphRelationshipOperations** (30 Min)
5. **GraphQueryService** (60 Min)
6. **GraphStoreService Facade** (45 Min)
7. **Tests** (60 Min)

**Total:** ~4.5 Stunden

---

**Status:** 📝 Plan erstellt  
**Next:** GraphIndexManager extrahieren

