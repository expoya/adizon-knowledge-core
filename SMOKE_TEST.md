# 🔥 Smoke Test - CRM Import Validation

**Status:** Ready for Testing  
**Datum:** 2026-01-09  
**Modus:** LIMIT 50 Records pro Entity

---

## 🎯 Ziel des Smoke Tests

Validieren, dass:
1. ✅ Alle COQL Queries funktionieren (keine `INVALID_QUERY` Errors)
2. ✅ Daten korrekt in Neo4j geschrieben werden
3. ✅ Feldnamen stimmen (owner_name, account_name, etc.)
4. ✅ Relationships korrekt erstellt werden
5. ✅ Keine kritischen Errors auftreten

**Erst danach:** LIMIT auf 10.000 erhöhen für Full Import

---

## ⚙️ Aktuelle Konfiguration

**Location:** `backend/app/integrations/zoho/provider.py:465-481`

```python
# SMOKE TEST Configuration
limit = 50          # 🔥 Records per entity
max_pages = 1       # 🔥 Only first page
```

**Erwartete Datenmengen:**
- Users: ~20 (alle, da < 50)
- Accounts: 50
- Leads: 50 (gefiltert > 2024-04-01)
- Contacts: 50
- Deals: 50
- Tasks: 50
- Notes: 50
- Events: 50
- Einwände: 50
- **Total: ~470 Nodes**

---

## 🚀 Deployment & Test Ablauf

### Step 1: Deploy Smoke Test Version

```bash
cd /Users/michaelschiestl/python/adizon-knowledge-core

git add backend/app/integrations/zoho/provider.py SMOKE_TEST.md
git commit -m "test: COQL smoke test with LIMIT 50

- Set LIMIT to 50 records per entity
- Disabled pagination (max_pages = 1)
- Fixed COQL queries (Einwände, Calendly, Deals)
- Added Leads date filter (> 2024-04-01)

Purpose: Validate queries before full import"

git push origin main
```

### Step 2: Trigger CRM Sync

Nach erfolgreichem Deployment:

```bash
curl -X POST https://your-domain.railway.app/api/v1/ingestion/crm-sync \
  -H "Content-Type: application/json" \
  -d '{
    "entity_types": [
      "Users",
      "Accounts", 
      "Contacts",
      "Leads",
      "Deals",
      "Tasks",
      "Notes",
      "Events",
      "Einwaende"
    ]
  }'
```

### Step 3: Monitor Logs

**Erwartete Log-Muster:**

✅ **SUCCESS:**
```
📥 Fetching skeleton data with graph schema
  📋 Processing Leads (module: Leads, label: Lead)...
    📅 Applying Leads filter: Created_Time > 2024-04-01
    🔥 SMOKE TEST MODE: LIMIT 50, max 1 page(s)
    📄 Page 1: Fetched 50 records (Total: 50)
    🔥 SMOKE TEST: Stopping after 1 page(s)
    ✅ Fetched 50 Leads
  
  📋 Processing Accounts (module: Accounts, label: Account)...
    🔥 SMOKE TEST MODE: LIMIT 50, max 1 page(s)
    📄 Page 1: Fetched 50 records (Total: 50)
    🔥 SMOKE TEST: Stopping after 1 page(s)
    ✅ Fetched 50 Accounts
```

❌ **ERRORS zu prüfen:**
```
# Diese sollten NICHT mehr auftauchen:
❌ Zoho API error: 400 - "INVALID_QUERY"
❌ column given seems to be invalid
❌ Status field nicht gefunden
❌ Leads.id ungültig
```

### Step 4: Validate in Neo4j

```cypher
// 1. Check Node Counts
MATCH (n)
RETURN labels(n)[0] AS label, count(*) AS count
ORDER BY count DESC

// Expected:
// Lead: 50
// Account: 50
// Contact: 50
// Deal: 50
// User: ~20
// Task: 50
// Note: 50
// CalendlyEvent: 50
// Einwand: 50
// Total: ~470 nodes

// 2. Check Relationships
MATCH ()-[r]->()
RETURN type(r) AS relationship, count(r) AS count
ORDER BY count DESC

// Expected relationships:
// HAS_OWNER: ~450 (most entities have owners)
// WORKS_AT: ~50 (contacts → accounts)
// HAS_DEAL: ~50 (accounts → deals)
// etc.

// 3. Validate Properties (RAG-ready)
MATCH (l:Lead)
RETURN l.name, l.owner_name, l.email, l.company
LIMIT 10

// Check that:
// ✅ l.name exists and is readable
// ✅ l.owner_name exists (flattened from lookup)
// ✅ Properties are not just IDs

// 4. Check Lead Date Filter
MATCH (l:Lead)
WHERE l.created_time IS NOT NULL
RETURN l.name, l.created_time
ORDER BY l.created_time ASC
LIMIT 10

// ✅ All leads should have created_time > 2024-04-01

// 5. Check for Orphaned Nodes
MATCH (n)
WHERE NOT (n)--()
RETURN labels(n)[0] AS label, count(n) AS orphaned
ORDER BY orphaned DESC

// Some orphans are OK (e.g. Users without relationships in sample)
// But should be minimal (<5%)
```

---

## ✅ Success Criteria für Smoke Test

### Logs
- [ ] Keine `INVALID_QUERY` Errors
- [ ] Alle Module zeigen "✅ Fetched X records"
- [ ] "🔥 SMOKE TEST MODE" Log erscheint
- [ ] Leads Filter wird angewendet
- [ ] Sync completed successfully

### Neo4j
- [ ] ~470 Nodes total
- [ ] 50 Nodes pro Entity (außer Users: ~20)
- [ ] Relationships existieren (~450+)
- [ ] Properties sind lesbar (nicht nur IDs)
- [ ] Leads haben created_time > 2024-04-01
- [ ] Keine massiven Orphaned Nodes

### Chatbot (optional)
- [ ] Chatbot findet Test-Entities
- [ ] `search_live_facts()` liefert Daten

---

## 🚦 Entscheidung nach Smoke Test

### ✅ PASS: Alles grün
→ **Weiter zu Full Import** (siehe unten)

### ⚠️ PARTIAL: Kleinere Issues
→ Fixes implementieren, erneut testen

### ❌ FAIL: Kritische Errors
→ Analyse, Bugfix, zurück zu Smoke Test

---

## 🔄 Full Import Aktivierung

**Nur wenn Smoke Test erfolgreich!**

### Änderungen für Full Import:

**File:** `backend/app/integrations/zoho/provider.py:465-481`

**Vorher (Smoke Test):**
```python
limit = 50          # 🔥 SMOKE TEST
max_pages = 1       # 🔥 SMOKE TEST
logger.info(f"    🔥 SMOKE TEST MODE: LIMIT {limit}, max {max_pages} page(s)")
```

**Nachher (Full Import):**
```python
limit = 10000       # ✅ PRODUCTION: Zoho COQL max per call
# Remove max_pages variable completely
# Remove smoke test log
# Remove the "if page >= max_pages" check in the loop
```

**Konkrete Änderungen:**

1. **Zeile 470:** `limit = 50` → `limit = 10000`
2. **Zeile 471:** `max_pages = 1` → **LÖSCHEN**
3. **Zeile 481:** `logger.info(f"    🔥 SMOKE TEST MODE...")` → **LÖSCHEN**
4. **Zeile 497-499:** Kompletter Block löschen:
   ```python
   # 🔥 SMOKE TEST: Stop after max_pages
   if page >= max_pages:
       logger.info(f"    🔥 SMOKE TEST: Stopping after {max_pages} page(s)")
       break
   ```

### Commit für Full Import:

```bash
git add backend/app/integrations/zoho/provider.py
git commit -m "feat: Enable full CRM import with pagination

Smoke test passed ✅
Changes:
- Increased LIMIT from 50 to 10000
- Removed max_pages limitation
- Enabled full pagination with OFFSET loop

Expected results:
- ~35,000 nodes total
- ~5,500 Leads (filtered)
- ~1,000 Accounts, Contacts, Deals
- Full data completeness"

git push origin main
```

---

## 📊 Full Import Erwartungen

Nach Aktivierung:

### Node Counts (geschätzt):
```cypher
Lead: ~5,500 (gefiltert > 2024-04-01)
Account: ~1,000
Contact: ~1,000
Deal: ~1,500
User: ~20
Task: ~1,000
Note: ~8,000
CalendlyEvent: ~1,000
Einwand: ~1,000
Attachment: ~500
Total: ~30,000-35,000 nodes
```

### Performance:
- **API Calls:** ~15-20 (mit Pagination)
- **Duration:** ~30-60 seconds
- **Rate Limited Delays:** ~10 seconds
- **Total Sync Time:** ~40-70 seconds

---

## 🐛 Troubleshooting

### Problem: "INVALID_QUERY" Errors
**Lösung:** Feldnamen in COQL Query prüfen
```python
# Check: provider.py search_live_facts()
# Ensure all field names match SCHEMA_MAPPING
```

### Problem: Keine Relationships
**Lösung:** Check lookup field extraction
```python
# Verify: properties have both _id and _name
# Example: owner_id, owner_name
```

### Problem: Leads haben alte Daten
**Lösung:** Date Filter prüfen
```python
# Line 477: where_clause should include Created_Time filter
```

### Problem: Zu wenige Nodes
**Lösung:** 
1. Check ob max_pages noch limitiert ist
2. Verify dass alle entity_types im Sync Request sind

---

## 📝 Checkliste

### Vor Smoke Test:
- [x] LIMIT auf 50 gesetzt
- [x] max_pages = 1 gesetzt
- [x] COQL Queries gefixt
- [x] Leads Filter implementiert
- [ ] Code committed & pushed
- [ ] Railway deployed

### Nach Smoke Test (wenn PASS):
- [ ] Logs überprüft (keine Errors)
- [ ] Neo4j Nodes gezählt (~470)
- [ ] Properties validiert
- [ ] Relationships geprüft
- [ ] LIMIT auf 10000 erhöht
- [ ] max_pages Check entfernt
- [ ] Full Import committed & deployed
- [ ] Final validation

---

**Status:** 🔥 Ready for Smoke Test  
**Next Action:** Commit → Deploy → Test → Validate → Full Import

