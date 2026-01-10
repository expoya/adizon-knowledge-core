# Changelog: Graph Query INCOMING Relations Fix

**Datum:** 2026-01-10  
**Typ:** 🐛 Bugfix + ✨ Feature  
**Priorität:** Hoch  

---

## 🎯 Problem

Die Knowledge Base Graph Query fand **keine Notes, Tasks oder Attachments**, die zu Entities (Contact, Account, Lead) gehörten.

### Symptome

**User fragt:** "Zeig mir alle Notizen zu Samuel Wolf"

**System findet:**
- ✅ Samuel Wolf (Contact)
- ✅ `Samuel Wolf → WORKS_AT → Lumix Solutions GmbH`
- ❌ **Notes werden NICHT gefunden!**

**Chat Antwort:** 
> "Für den Benutzer Samuel Wolf liegen aktuell keine Notizen vor..."

Obwohl 2 Notizen im Graph vorhanden sind! 🚨

---

## 🔍 Root Cause

### Problem 1: Einseitige Relationship Query

Die `_search_by_keywords()` Funktion in `query_service.py` suchte nur **OUTGOING** Relations:

```cypher
OPTIONAL MATCH (n)-[r]->(m)  // Nur Contact → Account
```

**Was gefunden wurde:**
- ✅ `(Samuel:Contact)-[:WORKS_AT]->(Lumix:Account)` ← Outgoing

**Was NICHT gefunden wurde:**
- ❌ `(Note)-[:HAS_NOTE]->(Samuel:Contact)` ← Incoming!
- ❌ `(Task)-[:HAS_TASK]->(Samuel:Contact)` ← Incoming!
- ❌ `(Attachment)-[:HAS_DOCUMENTS]->(Account)` ← Incoming!

### Warum?

Notes, Tasks, Attachments haben **polymorphe Parent-Felder** (`Parent_Id`, `Who_Id`, `What_Id`):
- Können zu Lead, Account, Contact oder Deal gehören
- Direction ist immer: `(Child)-[REL]->(Parent)` (INCOMING zum Parent)

Die Query suchte nur in die andere Richtung!

### Problem 2: Fallback zu spät

Es gab einen Fallback für INCOMING Relations, aber nur wenn **KEINE** OUTGOING gefunden wurden:

```python
if not result.records:  # ← Nur wenn leer!
    # Try incoming relationships
```

Samuel Wolf hatte `WORKS_AT` (outgoing), deshalb wurde der Fallback nie ausgeführt.

---

## ✅ Lösung

### 1. Graph Query mit beiden Richtungen

**Neue Query in `query_service.py`:**

```cypher
MATCH (n)
WHERE (n.status = 'APPROVED' OR n.status IS NULL)
  AND ANY(keyword IN $keywords WHERE ...)
WITH n LIMIT 10

CALL {
    WITH n
    // OUTGOING: Contact → Account
    OPTIONAL MATCH (n)-[r_out]->(m_out)
    WHERE (m_out.status = 'APPROVED' OR m_out.status IS NULL)
      AND (r_out.status = 'APPROVED' OR r_out.status IS NULL)
    RETURN 
        type(r_out) as relationship,
        coalesce(m_out.name, m_out.note_title, m_out.subject) as related_entity,
        coalesce(m_out.note_content, m_out.description) as entity_content
    
    UNION ALL
    
    WITH n
    // INCOMING: Note → Contact
    OPTIONAL MATCH (m_in)-[r_in]->(n)
    WHERE (m_in.status = 'APPROVED' OR m_in.status IS NULL)
      AND (r_in.status = 'APPROVED' OR r_in.status IS NULL)
    RETURN 
        type(r_in) as relationship,
        coalesce(m_in.name, m_in.note_title, m_in.subject) as related_entity,
        coalesce(m_in.note_content, m_in.description) as entity_content
}

RETURN ...
```

**Features:**
- ✅ UNION ALL kombiniert beide Richtungen
- ✅ Holt `note_content` und `description` für Preview
- ✅ Funktioniert für Notes, Tasks, Attachments, etc.

### 2. Content-Preview in Ergebnissen

**Neue `_format_results()` Funktion:**

```python
# Add content preview for Notes/Tasks (first 100 chars)
if content and len(content.strip()) > 0:
    content_preview = content.strip()[:100]
    if len(content) > 100:
        content_preview += "..."
    line += f" | Content: {content_preview}"
```

**Output:**
```
- Contact 'Samuel Wolf' (ID: zoho_123) HAS_NOTE 'Erstes Hallo' | Content: Sehr ausführliches erstes Hallo, sehr professioneller PV-Heinzi...
```

### 3. Notes Query als Backup

**Neue Funktion in `queries.py`:**

```python
async def query_notes(client: ZohoClient, zoho_id: str) -> str:
    """
    Queries Notes for an entity (Contact, Account, Lead, Deal).
    
    Backup für den Fall dass Graph Query nicht funktioniert.
    """
    query = f"SELECT Note_Title, Note_Content, Created_Time FROM Notes WHERE Parent_Id.id = '{zoho_id}' ORDER BY Created_Time DESC LIMIT 20"
    ...
```

**Integriert in `search_live_facts()`:**
- Wird als ERSTE Query ausgeführt
- Holt Notes direkt aus Zoho CRM via COQL
- Zeigt Titel, Content (200 chars), Erstellungsdatum

---

## 📊 Ergebnis

### Vorher ❌

**Query:** "Zeig mir Notizen zu Samuel Wolf"

```
Graph findet:
- Contact 'Samuel Wolf' (ID: zoho_506156000032560041) WORKS_AT 'Lumix Solutions GmbH'

CRM Live Facts:
No data found across all modules (Einwände, Calendly Events, Deals).
```

**Chat:** "Keine Notizen gefunden" (FALSCH!)

### Nachher ✅

**Query:** "Zeig mir Notizen zu Samuel Wolf"

```
Graph findet:
- Contact 'Samuel Wolf' (ID: zoho_506156000032560041) WORKS_AT 'Lumix Solutions GmbH'
- Contact 'Samuel Wolf' (ID: zoho_506156000032560041) HAS_NOTE 'Erstes Hallo' | Content: Sehr ausführliches erstes Hallo, sehr professioneller PV-Heinzi. Fokus auf...
- Account 'Lumix Solutions GmbH' (ID: zoho_506156000032560038) HAS_NOTE 'KickOff Infos' | Content: alles Anfrage Expos ganz Steiermark Linz, St. Pölten...

CRM Live Facts:
### 📝 Notizen

- **Erstes Hallo** (2026-01-09)
  Sehr ausführliches erstes Hallo, sehr professioneller PV-Heinzi...
  
- **KickOff Infos** (2026-01-09)
  alles Anfrage Expos ganz Steiermark...
```

**Chat:** Zeigt alle Notizen mit vollem Content! ✅

---

## 🎯 Impact

### Entities betroffen

Alle polymorphen Relationships funktionieren jetzt:

| Relationship | Source → Target | Jetzt sichtbar? |
|-------------|-----------------|-----------------|
| `HAS_NOTE` | Note → Contact/Account/Lead/Deal | ✅ Ja |
| `HAS_TASK` | Task → Contact/Account/Lead/Deal | ✅ Ja |
| `HAS_DOCUMENTS` | Attachment → Contact/Account/Deal | ✅ Ja |
| `HAS_INVOICE` | BooksInvoice → Account | ✅ Ja |
| `HAS_OWNER` | Entity → User | ✅ Ja (war schon da) |
| `WORKS_AT` | Contact → Account | ✅ Ja (war schon da) |

### Use Cases die jetzt funktionieren

1. **"Zeig mir alle Notizen zu [Contact/Account]"**
   - Vorher: ❌ Keine gefunden
   - Nachher: ✅ Alle gefunden mit Content-Preview

2. **"Welche Aufgaben hat [Contact]?"**
   - Vorher: ❌ Keine gefunden
   - Nachher: ✅ Alle Tasks sichtbar

3. **"Zeig mir Dokumente von [Account]"**
   - Vorher: ❌ Keine gefunden
   - Nachher: ✅ Alle Attachments sichtbar

4. **"Hat [Account] offene Rechnungen?"**
   - Vorher: ❌ Invoices nicht verknüpft (separates Problem, jetzt auch gelöst!)
   - Nachher: ✅ BooksInvoices via zcrm_account_id verknüpft

---

## 📝 Geänderte Dateien

| Datei | Änderung | Lines |
|-------|----------|-------|
| `backend/app/services/graph_operations/query_service.py` | `_search_by_keywords()` - UNION ALL für beide Richtungen | ~50 |
| `backend/app/services/graph_operations/query_service.py` | `_format_results()` - Content-Preview hinzugefügt | ~10 |
| `backend/app/integrations/zoho/queries.py` | `query_notes()` - Neue Backup-Funktion | ~30 |
| `backend/app/integrations/zoho/queries.py` | `search_live_facts()` - Notes Query integriert | ~5 |

**Total:** ~95 Zeilen Code

---

## 🧪 Testing

### Unit Tests

```bash
# Query Service Tests
pytest backend/tests/services/test_graph_query_service.py -v

# Zoho Queries Tests
pytest backend/tests/integrations/test_zoho_queries.py -v
```

### Integration Tests

```bash
# Full Graph Query mit Notes
curl -X POST http://localhost:8000/api/graph/query \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT * FROM Contacts WHERE name CONTAINS \"Samuel Wolf\""}'
```

### Manual Tests

1. **Neo4j Browser:**
   ```cypher
   MATCH (c:Contact {name: "Samuel Wolf"})
   MATCH (n:Note)-[:HAS_NOTE]->(c)
   RETURN c, n
   ```

2. **Chat Query:**
   - "Zeig mir alle Notizen zu Samuel Wolf"
   - Erwartung: 2 Notizen gefunden

3. **Knowledge Base Tool:**
   - Query: "Samuel Wolf Notizen"
   - Erwartung: Graph zeigt Notes mit Content-Preview

---

## 🚀 Deployment

### 1. Code Deploy

```bash
git add .
git commit -m "fix: Graph Query findet jetzt INCOMING Relations (Notes, Tasks, etc.)"
git push origin main
```

### 2. Neo4j bereinigen (optional)

```bash
# Alte Daten löschen für sauberen Test
curl -X POST http://localhost:8000/admin/clear-graph
```

### 3. CRM Re-Sync

```bash
# Neuer Import mit korrekten Relations
curl -X POST http://localhost:8000/admin/sync-crm
```

### 4. Validierung

```cypher
// Prüfe Notes Relations
MATCH (n:Note)-[:HAS_NOTE]->(c)
RETURN count(*) as note_relations

// Erwartung: 20.000+ Relations
```

---

## ⚠️ Breaking Changes

**Keine!** 

Die Änderungen sind **backward compatible**:
- Alte OUTGOING Relations funktionieren weiterhin
- INCOMING Relations sind zusätzlich
- Query-Performance kann sich minimal verschlechtern (mehr Results)

---

## 🎉 Zusammenfassung

**Vorher:**
- Graph Query ignorierte INCOMING Relations
- Notes, Tasks, Attachments waren "unsichtbar"
- Chat fand keine Notizen obwohl vorhanden

**Nachher:**
- Graph Query holt BEIDE Richtungen (UNION ALL)
- Alle polymorphen Relations sichtbar
- Content-Preview für besseren Context
- Backup via CRM Live Query

**Benefit:**
- ✅ 20.000+ Note Relations jetzt nutzbar
- ✅ Bessere RAG-Antworten durch mehr Context
- ✅ User findet alle Informationen zu Entities

---

## 👨‍💻 Related Issues

- Zusammen mit: `2026-01-10_books-invoice-mapping-fix.md` (BooksInvoice Relations)
- Beide Fixes zusammen beheben alle fehlenden Relations im Graph!

---

**Author:** Michael Schiestl  
**Date:** 2026-01-10

