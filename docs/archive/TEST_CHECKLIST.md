# ✅ Test Checklist - Smoke Test → Full Import

## 🔥 Phase 1: Smoke Test (JETZT)

### Configuration
```python
limit = 50          # ← Smoke Test
max_pages = 1       # ← Nur erste Page
```

### Expected Results
- **Nodes:** ~470 total
- **Per Entity:** 50 (außer Users: ~20)
- **Duration:** ~10 seconds

### Validation Steps

#### 1. Deploy & Sync
```bash
# Deploy
git add backend/app/integrations/zoho/provider.py SMOKE_TEST.md TEST_CHECKLIST.md PHASE1_COMPLETE.md
git commit -m "test: COQL smoke test with LIMIT 50"
git push origin main

# Wait for Railway deployment...

# Trigger Sync
curl -X POST https://your-domain/api/v1/ingestion/crm-sync \
  -H "Content-Type: application/json" \
  -d '{"entity_types": ["Users","Accounts","Contacts","Leads","Deals","Tasks","Notes","Events","Einwaende"]}'
```

#### 2. Check Logs ✅ / ❌
```
□ Keine "INVALID_QUERY" Errors
□ Keine "column given seems to be invalid" 
□ "🔥 SMOKE TEST MODE" erscheint
□ "📄 Page 1: Fetched 50 records"
□ "✅ Fetched 50 Accounts/Leads/..."
□ Leads Filter aktiv: "📅 Applying Leads filter"
```

#### 3. Check Neo4j ✅ / ❌
```cypher
// Node Counts
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count ORDER BY count DESC
□ Lead: 50
□ Account: 50
□ Contact: 50
□ Deal: 50
□ Task: 50
□ Note: 50
□ User: ~20
□ Total: ~470

// Relationships
MATCH ()-[r]->() RETURN type(r), count(r) ORDER BY count(r) DESC
□ HAS_OWNER: >0
□ WORKS_AT: >0
□ HAS_DEAL: >0
□ Mindestens 3 Relationship-Typen

// Properties Check
MATCH (l:Lead) RETURN l.name, l.owner_name, l.email LIMIT 5
□ l.name ist lesbar (nicht NULL)
□ l.owner_name existiert (flattened)
□ Felder sind nicht nur IDs

// Date Filter Check
MATCH (l:Lead) WHERE l.created_time IS NOT NULL 
RETURN l.created_time ORDER BY l.created_time LIMIT 1
□ Ältestes Lead ist nach 2024-04-01
```

#### 4. Decision Point 🚦

**✅ ALLE Checks grün?**
→ Weiter zu **Phase 2: Full Import**

**⚠️ Manche Checks gelb?**
→ Analyse, Minor Fixes, re-test

**❌ Kritische Errors?**
→ Debugging, Bugfix, zurück zu Smoke Test

---

## 🚀 Phase 2: Full Import (NACH erfolgreichem Smoke Test)

### Configuration Changes

**File:** `backend/app/integrations/zoho/provider.py`

#### Änderung 1: Line ~470
```python
# VORHER:
limit = 50  # 🔥 SMOKE TEST

# NACHHER:
limit = 10000  # ✅ PRODUCTION: Zoho COQL max per call
```

#### Änderung 2: Line ~471
```python
# VORHER:
max_pages = 1  # 🔥 SMOKE TEST

# NACHHER:
# (Diese Zeile komplett LÖSCHEN)
```

#### Änderung 3: Line ~481
```python
# VORHER:
logger.info(f"    🔥 SMOKE TEST MODE: LIMIT {limit}, max {max_pages} page(s)")

# NACHHER:
# (Diese Zeile komplett LÖSCHEN)
```

#### Änderung 4: Line ~497-499
```python
# VORHER:
# 🔥 SMOKE TEST: Stop after max_pages
if page >= max_pages:
    logger.info(f"    🔥 SMOKE TEST: Stopping after {max_pages} page(s)")
    break

# NACHHER:
# (Diesen kompletten Block LÖSCHEN)
```

### Expected Results
- **Nodes:** ~30,000-35,000 total
- **Leads:** ~5,500 (gefiltert > 2024-04-01)
- **Duration:** ~40-70 seconds

### Deployment
```bash
git add backend/app/integrations/zoho/provider.py
git commit -m "feat: Enable full CRM import with pagination

Smoke test passed ✅

Changes:
- LIMIT 50 → 10000
- Removed max_pages limitation
- Full pagination enabled

Expected: ~35k nodes total"

git push origin main
```

### Validation Steps

#### 1. Trigger Full Sync
```bash
curl -X POST https://your-domain/api/v1/ingestion/crm-sync \
  -H "Content-Type: application/json" \
  -d '{"entity_types": ["Users","Accounts","Contacts","Leads","Deals","Tasks","Notes","Events","Einwaende","Attachments"]}'
```

#### 2. Monitor Logs ✅ / ❌
```
□ Mehrere Pages: "📄 Page 1, Page 2, Page 3..."
□ Leads: "📄 Page 2: Fetched X records (Total: 15500)"
□ Accounts: "📄 Page 1: Fetched 1000 records"
□ Duration: < 2 Minuten
□ "✅ Total skeleton data fetched: 35000 records"
□ Keine kritischen Errors
```

#### 3. Check Neo4j ✅ / ❌
```cypher
// Full Counts
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count ORDER BY count DESC
□ Lead: ~5,500
□ Account: ~1,000
□ Contact: ~1,000
□ Deal: ~1,500
□ Note: ~8,000
□ Total: ~30,000-35,000

// Compare with Zoho UI
// Go to: Zoho CRM → Reports → Leads
□ Neo4j Lead count ≈ Zoho filtered count (±5%)
□ Neo4j Account count ≈ Zoho Account count (±5%)

// Relationship Density
MATCH ()-[r]->() RETURN count(r) AS total_relationships
□ Total relationships > 30,000
□ Avg 1+ relationships per node
```

#### 4. Chatbot Test ✅ / ❌
```
User: "Zeige mir alle Accounts"
□ Chatbot findet Entities (keine "nicht gefunden")

User: "Was weißt du über Lead XYZ?"
□ search_live_facts() liefert Daten
□ Keine COQL Errors in Logs

User: "Welche Deals hat Account ABC?"
□ Richtige Daten aus Graph
```

---

## 📊 Quick Reference

| Phase | Limit | Pages | Nodes | Duration | Purpose |
|-------|-------|-------|-------|----------|---------|
| **Smoke Test** | 50 | 1 | ~470 | ~10s | Validation |
| **Full Import** | 10000 | Multi | ~35k | ~60s | Production |

---

## 🐛 Troubleshooting Guide

### Smoke Test Fails

#### Error: "INVALID_QUERY - column Status invalid"
**File:** `provider.py` → `search_live_facts()`
**Fix:** Feldname in Query korrigieren (bereits implementiert)

#### Error: "No nodes created"
**Check:** CRM Sync Response
```bash
# Response sollte zeigen:
{
  "entities_synced": 470,
  "entities_created": 470,
  "status": "success"
}
```

#### Error: "Leads Filter nicht aktiv"
**Check:** Log muss zeigen:
```
📅 Applying Leads filter: Created_Time > 2024-04-01
```

### Full Import Issues

#### Problem: "Sync dauert > 5 Minuten"
**Mögliche Ursachen:**
- Rate Limit zu konservativ (0.6s zu lang)
- Netzwerk-Latenz
- Zoho API langsam

**Fix:** Monitor, aber normal für erste volle Sync

#### Problem: "Nur 10,000 Leads statt 5,500"
**Ursache:** Date Filter nicht aktiv
**Fix:** Check `where_clause` in Line ~477

#### Problem: "Pagination stoppt nach Page 1"
**Ursache:** `max_pages` Check noch aktiv
**Fix:** Verifiziere dass Block in Line 497-499 gelöscht ist

---

## ✅ Final Checklist

### Smoke Test Complete
- [ ] Logs sauber (keine INVALID_QUERY)
- [ ] ~470 Nodes in Neo4j
- [ ] Properties lesbar
- [ ] Relationships vorhanden
- [ ] Entscheidung: GO für Full Import

### Full Import Complete
- [ ] Code geändert (LIMIT 10000, max_pages removed)
- [ ] Deployed & Synced
- [ ] ~35k Nodes in Neo4j
- [ ] Counts stimmen mit Zoho überein
- [ ] Chatbot funktioniert
- [ ] Documentation updated

### Production Ready
- [ ] Monitoring aktiv
- [ ] LangSmith Tracing funktioniert
- [ ] Backup erstellt
- [ ] Team informiert

---

**Current Status:** 🔥 Ready for Smoke Test  
**Next Action:** Deploy → Test → Validate → (if ✅) → Full Import

