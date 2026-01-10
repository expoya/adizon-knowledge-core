# LLM-basierte Entity Extraction & COQL Syntax Fix

**Datum:** 2026-01-10  
**Typ:** 🔧 Bug Fix + ✨ Feature Enhancement  
**Betrifft:** `chat_workflow.py`, `queries.py`

## Problem

1. **Entity Resolution versagte komplett:**
   - User fragt nach "Lumix Solutions GmbH" → System findet "Julita Szumska" 
   - User fragt nach "Samuel Wolf" → System findet völlig falsche Entities
   - Grund: Simplistische Cypher Query mit `CONTAINS` und `LIMIT 1` ohne Scoring
   - Query versuchte die gesamte User-Anfrage mit Entity-Namen zu matchen

2. **Notes Query schlug mit INVALID_QUERY fehl:**
   - Zoho COQL versteht `Parent_Id.id` nicht
   - Richtig: `Parent_Id` (ohne `.id` Suffix)

## Lösung

### 1. LLM-basierte Entity Extraction (🎯 Präzision!)

**Neues Prompt:** `entity_extraction.txt`
- LLM extrahiert ALLE Personen-/Firmen-Namen aus User-Anfrage
- Output: JSON-Array mit exakten Namen
- Keine Pronomen, keine generischen Begriffe

**Beispiel:**
```
User: "Welche Notizen haben wir zu Samuel Wolf oder Lumix Solutions GmbH?"
LLM Output: ["Samuel Wolf", "Lumix Solutions GmbH"]
```

### 2. Zweistufiges Entity Resolution (Router + Knowledge Node)

**STEP 1: LLM Entity Extraction**
```python
llm.ainvoke([SystemMessage(content=entity_extraction_prompt.format(query=user_message))])
# → Extrahiert exakte Namen aus der Anfrage
```

**STEP 2: Einfache Graph-Suche mit extrahierten Namen**
```cypher
// Exact Match (Score: 100)
MATCH (n)
WHERE n.source_id STARTS WITH 'zoho_'
  AND (
    toLower(n.name) = toLower($name)
    OR toLower(n.company) = toLower($name)
    OR toLower(n.account_name) = toLower($name)
    OR (toLower(n.first_name) + ' ' + toLower(n.last_name)) = toLower($name)
  )
RETURN n.source_id, n.name, labels(n)[0] as type, 100 as score

UNION

// Fallback: Partial Match (Score: 50)
MATCH (n)
WHERE n.source_id STARTS WITH 'zoho_'
  AND (
    toLower(n.name) CONTAINS toLower($name)
    OR toLower(n.company) CONTAINS toLower($name)
    OR toLower(n.account_name) CONTAINS toLower($name)
  )
RETURN n.source_id, n.name, labels(n)[0] as type, 50 as score

ORDER BY score DESC LIMIT 3
```

**STEP 3: Best Match Selection**
- Sortiert nach Score (100 = exakt, 50 = partial)
- Bei Score < 100 → `entity_uncertain = True`
- Logging aller Candidates für Transparenz

### 3. COQL Syntax Fix für Notes

**Vorher (❌ Fehlgeschlagen):**
```sql
SELECT Note_Title, Note_Content, Created_Time 
FROM Notes 
WHERE Parent_Id.id = '506156000032560038'  -- ❌ INVALID_QUERY
```

**Nachher (✅ Funktioniert):**
```sql
SELECT Note_Title, Note_Content, Created_Time 
FROM Notes 
WHERE Parent_Id = '506156000032560038'  -- ✅ Korrekte COQL Syntax
```

## Geänderte Dateien

### 1. `backend/app/prompts/entity_extraction.txt` (NEU)
- LLM Prompt für Named Entity Recognition
- Extrahiert Namen aus User-Anfragen
- JSON-Array Output

### 2. `backend/app/graph/chat_workflow.py`

**`router_node` (Zeilen ~87-184):**
- Ersetzt simplistische CONTAINS-Query
- Integriert LLM Entity Extraction
- Sucht mit extrahierten Namen im Graph
- Logging für Transparenz

**`knowledge_node` (Zeilen ~292-380):**
- Gleiche LLM-basierte Entity Extraction
- Multi-Entity Support (alle extrahierten Namen)
- Best Match Selection mit Scoring

### 3. `backend/app/integrations/zoho/queries.py`

**`query_notes` (Zeile 155):**
```python
# Vorher:
query = f"... WHERE Parent_Id.id = '{zoho_id}' ..."

# Nachher:
query = f"... WHERE Parent_Id = '{zoho_id}' ..."
```

## Erwartetes Verhalten

### Vorher (❌)
```
User: "Welche Notizen haben wir zu Lumix Solutions GmbH?"
System: [Findet "Julita Szumska" - falsch!]
Response: "Keine Notizen gefunden."
```

### Nachher (✅)
```
User: "Welche Notizen haben wir zu Lumix Solutions GmbH?"

Log:
  🔍 Step 1: Extracting entity names from query using LLM...
    ✅ LLM extracted 1 entity names: ['Lumix Solutions GmbH']
  🔍 Step 2: Searching graph for extracted entities...
    ✅ Found 1 matches for 'Lumix Solutions GmbH'
  🎯 Best match: Account 'Lumix Solutions GmbH' (Score: 100)

Response: [Zeigt alle Notizen zu Lumix Solutions GmbH]
```

## Testing

**Manuelle Tests:**
1. ✅ "Welche Notizen haben wir zu Samuel Wolf?"
   - Sollte Notes zu Contact "Samuel Wolf" finden
2. ✅ "Zeig mir Rechnungen von Lumix Solutions GmbH"
   - Sollte BooksInvoices zum Account finden
3. ✅ "Was wissen wir über Andreas Wolf und ACME Corp?"
   - Sollte beide Entities extrahieren und suchen
4. ✅ "Wie viele Leads haben wir insgesamt?"
   - Sollte KEINE Entity-Extraktion triggern (keine Namen)

**Live Facts Test:**
```bash
# Notes sollten jetzt über COQL fetchbar sein
curl -X POST /chat \
  -d '{"message": "Welche Notizen gibt es zu Samuel Wolf?"}'
```

## Migration / Rollout

✅ **Keine Breaking Changes**
- Backwards-kompatibel
- Kein DB-Schema Change
- Keine API-Änderungen

**Empfohlene Schritte:**
1. Deploy Code
2. Neo4j bereinigen: `MATCH (n) DETACH DELETE n`
3. Full CRM Sync durchführen
4. Testen mit bekannten Entities

## Hinweise

- **LLM Entity Extraction ist robust:** 
  - Erkennt verschiedene Schreibweisen
  - Filtert Pronomen und generische Begriffe
  - Behält Original-Formatierung bei

- **Graph-Query ist jetzt präzise:**
  - Exact Match wird bevorzugt (Score: 100)
  - Fallback auf Partial Match nur wenn nötig (Score: 50)
  - Multi-Field Search (name, company, account_name, first_name+last_name)

- **Logging für Debugging:**
  - Alle extrahierten Entity-Namen werden geloggt
  - Alle gefundenen Matches werden geloggt
  - Best Match wird mit Score angezeigt

## Siehe auch

- [2026-01-10_books-invoice-mapping-fix.md](./2026-01-10_books-invoice-mapping-fix.md) - Invoice Linking Fix
- [2026-01-10_graph-query-incoming-relations-fix.md](./2026-01-10_graph-query-incoming-relations-fix.md) - Incoming Relations Fix
- [GRAPH_SCHEMA.md](../GRAPH_SCHEMA.md) - Knowledge Graph Schema
- [AGENTIC_RAG.md](../AGENTIC_RAG.md) - RAG Architektur

---

**Status:** ✅ Implementiert  
**Autor:** Michael Schiestl  
**Review:** Pending

