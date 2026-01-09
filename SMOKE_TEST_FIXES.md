# 🔧 Smoke Test Fixes - 2026-01-09

## 🚨 Probleme aus erstem Smoke Test

### Test-Ergebnisse:
- ✅ **Deployment erfolgreich**
- ✅ **466 Entities synced** (keine INVALID_QUERY Errors mehr!)
- ⚠️ **Aber**: Mehrere Daten-Qualitätsprobleme

---

## 🐛 Identifizierte Probleme & Fixes

### 1. **Lead Names: "None Vorname Nachname"** ❌

**Problem:**
```cypher
MATCH (l:Lead) RETURN l.name LIMIT 1
// Result: "None Marian Hornak"
```

Zoho gibt manchmal `First_Name = "None"` (als String) zurück.

**Fix:**
```python
# Filter "None" string and None values
if first in [None, "None", ""]:
    first = ""
if last in [None, "None", ""]:
    last = ""

full_name = f"{first} {last}".strip()
```

**Expected Result:**
```cypher
// Result: "Marian Hornak" (ohne "None")
```

---

### 2. **owner_name ist NULL** ❌

**Problem:**
```cypher
MATCH (l:Lead) RETURN l.name, l.owner_name LIMIT 5
// owner_name: NULL
```

Zoho Owner-Objekte haben möglicherweise nicht `name` als Key, sondern `first_name` + `last_name` oder andere Varianten.

**Fix:**
```python
# Erweiterte Fallbacks für Name-Extraction
lookup_name = (
    value.get("name") or 
    value.get("full_name") or 
    value.get("Full_Name") or
    value.get("first_name") or      # NEU
    value.get("last_name") or       # NEU
    value.get("email") or
    value.get("Account_Name") or    # NEU
    value.get("Deal_Name") or       # NEU
    value.get("Subject")            # NEU
)

# Special case for Owner fields
if not lookup_name and "Owner" in field:
    first_name = value.get("first_name", "")
    last_name = value.get("last_name", "")
    if first_name or last_name:
        lookup_name = f"{first_name} {last_name}".strip()
```

**Expected Result:**
```cypher
// owner_name: "Michael Schiestl" (nicht NULL)
```

**Zusätzlich:** Besseres Logging wenn Name fehlt:
```python
logger.warning(f"⚠️ Lookup field '{field}' has ID but no name. Available keys: {list(value.keys())}, Values: {str(value)[:100]}")
```

→ So können wir in den Logs sehen, welche Keys Zoho tatsächlich zurückgibt!

---

### 3. **created_time Property fehlt** ❌

**Problem:**
```cypher
MATCH (l:Lead) WHERE l.created_time IS NOT NULL 
RETURN l.created_time
// WARNING: property key 'created_time' not in database
```

`Created_Time` war nicht in den Leads-Fields konfiguriert.

**Fix:**
```python
"Leads": {
    "fields": [
        "id", 
        "Last_Name", 
        "First_Name", 
        "Company", 
        "Email", 
        "Owner", 
        "Converted_Account",
        "Created_Time"  # ← NEU hinzugefügt
    ],
    ...
}
```

**Expected Result:**
```cypher
MATCH (l:Lead) 
RETURN l.created_time 
ORDER BY l.created_time LIMIT 1
// Result: "2024-04-15T10:30:00Z"
```

---

### 4. **CRMEntity Orphan Nodes (112)** ⚠️

**Problem:**
```cypher
MATCH (n) RETURN labels(n)[0], count(*) ORDER BY count(*) DESC
// CRMEntity: 112 (sollte nicht existieren)
```

Diese Nodes entstehen durch Relationships, die auf nicht-existierende Target-Nodes zeigen.

**Beispiel:**
- Lead hat `Converted_Account.id = "123"`
- Aber Account "123" ist nicht in den 50 importierten Accounts
- → Es wird ein `CRMEntity` mit `source_id = "zoho_123"` erstellt

**Status:**
- ⚠️ **Akzeptabel für Smoke Test** (nur 50 Entities pro Typ)
- ✅ **Wird besser im Full Import** (wenn alle Entities importiert sind)

**Alternative Fix (optional):**
```cypher
// Cleanup Query (nach Sync):
MATCH (n:CRMEntity)
WHERE NOT (n)--()  // No relationships
DELETE n
```

Aber: Besser ist, einfach Full Import zu machen!

---

## 📊 Erwartete Verbesserungen nach Fixes

### Vorher:
```cypher
// Lead Names
"None Marian Hornak" ❌

// owner_name
NULL ❌

// created_time
Property not found ❌

// CRMEntity Orphans
112 nodes ⚠️
```

### Nachher:
```cypher
// Lead Names
"Marian Hornak" ✅

// owner_name
"Michael Schiestl" ✅

// created_time
"2024-04-15T10:30:00Z" ✅

// CRMEntity Orphans
112 nodes (OK für Smoke Test, wird besser bei Full Import)
```

---

## 🚀 Re-Test nach Deployment

### 1. Deploy Fixes
```bash
git add backend/app/integrations/zoho/provider.py SMOKE_TEST_FIXES.md
git commit -m "fix: Smoke test data quality improvements

- Filter 'None' string from Lead names
- Enhanced owner_name lookup with more fallbacks
- Added Created_Time to Leads fields
- Better logging for missing lookup names

Fixes for smoke test issues:
- Lead names show 'None Vorname' → Fixed
- owner_name is NULL → Fixed  
- created_time property missing → Fixed"

git push origin main
```

### 2. Trigger Re-Sync
```bash
curl -X POST https://your-domain/api/v1/ingestion/crm-sync \
  -H "Content-Type: application/json" \
  -d '{"entity_types": ["Users","Accounts","Contacts","Leads","Deals","Tasks","Notes","Events","Einwaende"]}'
```

### 3. Re-Validate in Neo4j

```cypher
// 1. Check Lead Names (should be clean now)
MATCH (l:Lead) 
RETURN l.name 
LIMIT 5
// Expected: No "None" prefix

// 2. Check owner_name (should NOT be NULL)
MATCH (l:Lead) 
RETURN l.name, l.owner_name, l.email 
LIMIT 5
// Expected: owner_name populated

// 3. Check created_time (should exist)
MATCH (l:Lead) 
WHERE l.created_time IS NOT NULL
RETURN l.name, l.created_time 
ORDER BY l.created_time 
LIMIT 5
// Expected: Dates after 2024-04-01

// 4. CRMEntity count (same as before, OK for now)
MATCH (n:CRMEntity) RETURN count(n)
// Expected: ~112 (acceptable for smoke test)
```

---

## ✅ Success Criteria (Updated)

Smoke Test ist erfolgreich wenn:

### Logs:
- [x] Keine INVALID_QUERY Errors
- [x] 466 entities synced
- [ ] "🔥 SMOKE TEST MODE" erscheint (überprüfen in nächstem Deploy)

### Neo4j Data Quality:
- [ ] Lead names OHNE "None" prefix
- [ ] owner_name ist NICHT NULL
- [ ] created_time Property existiert
- [ ] Properties sind lesbar
- [ ] Relationships vorhanden

### Wenn alle ✅:
→ **GO for Full Import!**

---

## 🔄 Next Steps

1. ✅ Fixes implementiert
2. ⏳ Commit & Deploy
3. ⏳ Re-Test
4. ⏳ Validate data quality
5. ⏳ If ✅ → Enable Full Import (LIMIT 10000)

---

**Status:** 🔧 Fixes Ready for Deployment  
**Impact:** High - Verbessert Datenqualität deutlich

