# 🔥 SMOKE TEST - Quick Start Guide

## 🎯 Was ist das?

**Smoke Test = Sichere Validierung mit LIMIT 50**

Statt direkt 35.000 Nodes zu importieren, testen wir erst mit **50 Nodes pro Entity**, um:
- ✅ COQL Queries zu validieren (keine Errors)
- ✅ Neo4j Schema zu prüfen (Properties korrekt)
- ✅ Relationships zu testen (korrekt verlinkt)
- ✅ Chatbot Funktion zu checken

**Erst nach erfolgreichem Smoke Test:** LIMIT auf 10.000 erhöhen für Full Import

---

## 🚀 Quick Start (3 Schritte)

### 1️⃣ Deploy Smoke Test

```bash
cd /Users/michaelschiestl/python/adizon-knowledge-core

git add .
git commit -m "test: COQL smoke test with LIMIT 50"
git push origin main
```

**Warten auf:** Railway Deployment ✅

---

### 2️⃣ Trigger Sync

```bash
curl -X POST https://your-domain.railway.app/api/v1/ingestion/crm-sync \
  -H "Content-Type: application/json" \
  -d '{"entity_types": ["Users","Accounts","Contacts","Leads","Deals","Tasks","Notes","Events","Einwaende"]}'
```

**Erwartete Response:**
```json
{
  "status": "success",
  "entities_synced": 470,
  "entities_created": 470,
  "message": "CRM Sync completed successfully: 470 entities synced"
}
```

---

### 3️⃣ Validate in Neo4j

```cypher
// Quick Check: Node Counts
MATCH (n)
RETURN labels(n)[0] AS label, count(*) AS count
ORDER BY count DESC

// Expected:
// Lead: 50
// Account: 50
// Contact: 50
// Deal: 50
// ...
// Total: ~470
```

**✅ Alles OK?**  
→ Siehe `TEST_CHECKLIST.md` für Full Import Aktivierung

**❌ Errors?**  
→ Siehe `SMOKE_TEST.md` → Troubleshooting

---

## 📋 Files Übersicht

| File | Zweck |
|------|-------|
| **README_SMOKE_TEST.md** | Diese Datei - Quick Start |
| **TEST_CHECKLIST.md** | Detaillierte Checkliste Smoke → Full |
| **SMOKE_TEST.md** | Vollständige Dokumentation |
| **PHASE1_COMPLETE.md** | Technische Details |

---

## 🔄 Nach Smoke Test: Full Import

**Wenn alles grün ist:**

1. **Code ändern:**
   ```python
   # In provider.py Line 470-471:
   limit = 10000  # ← Change from 50
   # Remove max_pages line completely
   ```

2. **Deploy:**
   ```bash
   git commit -m "feat: Enable full import with 10k limit"
   git push
   ```

3. **Re-Sync:**
   - Trigger erneut
   - Warte ~60 Sekunden
   - Validate: ~35k Nodes

**Details:** Siehe `TEST_CHECKLIST.md` Phase 2

---

## 🆘 Hilfe

### Logs prüfen
```bash
# Railway Dashboard → Deployment → Logs
# Suche nach:
- "INVALID_QUERY" (sollte NICHT da sein)
- "🔥 SMOKE TEST MODE" (sollte erscheinen)
- "✅ Fetched 50 Accounts" (sollte erscheinen)
```

### Neo4j prüfen
```cypher
// Sind Daten da?
MATCH (n) RETURN count(n)

// Sind Properties OK?
MATCH (l:Lead) RETURN l LIMIT 1
```

### Chatbot testen
```
User: "Zeige mir Accounts"
→ Sollte funktionieren (keine Errors)
```

---

**Status:** 🔥 Ready to Deploy!  
**Next:** Deploy → Sync → Validate → Full Import

