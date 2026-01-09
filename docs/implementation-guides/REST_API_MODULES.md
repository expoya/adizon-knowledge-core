# 🆕 REST API Support für Finance & Email Modules

## 🎯 Implementiert

### Neue Module:
1. **Invoices** (Zoho Finance) ✅
2. **Subscriptions** (Zoho Finance) ✅
3. **Emails** (Zoho Activities) ✅

---

## 🔧 Was wurde geändert

### 1. Neue REST API Methode

**File:** `backend/app/integrations/zoho/provider.py`

```python
async def fetch_via_rest_api(
    self,
    module_name: str,
    fields: List[str],
    limit: int = 200,
    page: int = 1
) -> List[Dict[str, Any]]:
    """
    Fetches records via Zoho REST API (for modules that don't support COQL).
    
    Used for: Invoices, Subscriptions, Emails, and other Finance/Activity modules.
    """
```

**Features:**
- Pagination support (max 200 per page)
- Field selection
- Error handling
- Rate limit protection

---

### 2. SCHEMA_MAPPING Erweiterungen

#### Invoices (neu konfiguriert):
```python
"Invoices": {
    "label": "Invoice",
    "module_name": "Invoices",  # ← Korrigiert von "Zoho_Books"
    "fields": [
        "id", 
        "Subject", 
        "Account_Name",  # ← Korrigiert von "Account"
        "Grand_Total",   # ← Korrigiert von "Total"
        "Status", 
        "Invoice_Date"   # ← NEU
    ],
    "relations": [
        {"field": "Account_Name", "edge": "HAS_INVOICE", "target_label": "Account", "direction": "INCOMING"}
    ],
    "use_rest_api": True  # ← NEU: Flag für REST API
}
```

#### Subscriptions (neu konfiguriert):
```python
"Subscriptions": {
    "label": "Subscription",
    "module_name": "Subscriptions",  # ← Korrigiert von "Subscriptions__s"
    "fields": [
        "id", 
        "Name", 
        "Account_Name",  # ← Korrigiert von "Account"
        "Amount",        # ← Korrigiert von "Total"
        "Status", 
        "Start_Date"     # ← NEU
    ],
    "relations": [
        {"field": "Account_Name", "edge": "HAS_SUBSCRIPTION", "target_label": "Account", "direction": "INCOMING"}
    ],
    "use_rest_api": True  # ← NEU
}
```

#### Emails (komplett neu):
```python
"Emails": {
    "label": "Email",
    "module_name": "Emails",
    "fields": [
        "id", 
        "Subject", 
        "from", 
        "to", 
        "Parent_Id", 
        "Owner"
    ],
    "relations": [
        {"field": "Parent_Id", "edge": "HAS_EMAIL", "target_label": "CRMEntity", "direction": "INCOMING"},
        {"field": "Owner", "edge": "HAS_OWNER", "target_label": "User", "direction": "OUTGOING"}
    ],
    "use_rest_api": True  # ← NEU
}
```

---

### 3. Fetch-Logik Anpassung

**Dual Mode Support:**

```python
if use_rest_api:
    # REST API Fetch
    data = await fetch_via_rest_api(...)
else:
    # COQL Fetch (existing)
    data = await execute_raw_query(...)

# Then: Process data (gemeinsam)
```

**Features:**
- Automatische Erkennung via `use_rest_api` Flag
- Gleiche Pagination wie COQL
- Rate Limit Protection (0.6s zwischen Calls)
- Error Recovery

---

## 📊 Smoke Test Erwartungen

### Neue Node Types:
```
Invoice: 50 (max verfügbar)
Subscription: 50 (max verfügbar)  
Email: 50 (max verfügbar)
```

### Relationships:
```
HAS_INVOICE: Account → Invoice
HAS_SUBSCRIPTION: Account → Subscription
HAS_EMAIL: Lead/Account/Contact → Email
```

### Total Impact:
```
Vorher: ~452 nodes
Nachher: ~602 nodes (+150 Finance/Email nodes)
```

---

## 🚀 Deployment & Test

### 1. Commit & Deploy
```bash
git add backend/app/integrations/zoho/provider.py REST_API_MODULES.md
git commit -m "feat: Add REST API support for Invoices, Subscriptions, Emails"
git push origin main
```

### 2. Clear Neo4j
```cypher
MATCH (n)
DETACH DELETE n
```

### 3. Trigger Sync mit neuen Modulen
```bash
curl -X POST https://your-domain/api/v1/ingestion/crm-sync \
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
      "Einwaende",
      "Attachments",
      "Invoices",
      "Subscriptions",
      "Emails"
    ]
  }'
```

### 4. Validate in Neo4j
```cypher
// Check new node types
MATCH (n)
RETURN labels(n)[0] AS label, count(*) AS count
ORDER BY count DESC

// Expected additional:
// Invoice: ~50
// Subscription: ~50  
// Email: ~50

// Check new relationships
MATCH ()-[r:HAS_INVOICE]->()
RETURN count(r)

MATCH ()-[r:HAS_SUBSCRIPTION]->()
RETURN count(r)

MATCH ()-[r:HAS_EMAIL]->()
RETURN count(r)
```

---

## 🎨 Use Cases

### 1. Rechnungen zu Account
```cypher
MATCH (a:Account {name: "Voltage GmbH"})-[:HAS_INVOICE]-(i:Invoice)
RETURN i.subject, i.grand_total, i.status, i.invoice_date
ORDER BY i.invoice_date DESC
```

### 2. Subscriptions zu Account
```cypher
MATCH (a:Account {name: "Voltage GmbH"})-[:HAS_SUBSCRIPTION]-(s:Subscription)
RETURN s.name, s.amount, s.status, s.start_date
ORDER BY s.start_date DESC
```

### 3. Email-Verlauf zu Lead
```cypher
MATCH (l:Lead {email: "test@example.com"})-[:HAS_EMAIL]-(e:Email)
RETURN e.subject, e.from, e.to
ORDER BY e.created_at DESC
LIMIT 20
```

### 4. Account mit Finance-Übersicht
```cypher
MATCH (a:Account {name: "Voltage GmbH"})
OPTIONAL MATCH (a)-[:HAS_INVOICE]-(i:Invoice)
OPTIONAL MATCH (a)-[:HAS_SUBSCRIPTION]-(s:Subscription)
RETURN 
    a.name,
    count(DISTINCT i) as total_invoices,
    sum(i.grand_total) as total_invoice_amount,
    count(DISTINCT s) as total_subscriptions,
    sum(s.amount) as total_subscription_amount
```

---

## 🔄 Von Smoke Test zu Full Import

**Nach erfolgreichem Smoke Test:**

### Änderungen für Full Import:

#### REST API Modules (Lines ~540-560):
```python
# VORHER (Smoke Test):
rest_limit = 50  # 🔥 SMOKE TEST
while page_num <= 1:  # 🔥 SMOKE TEST: Only 1 page

# NACHHER (Full Import):
rest_limit = 200  # ✅ REST API max per page
while True:  # ✅ All pages
    if len(data_page) < rest_limit:
        break  # Last page
```

#### COQL Modules (Lines ~576-578):
```python
# VORHER (Smoke Test):
limit = 50  # 🔥 SMOKE TEST
max_pages = 1  # 🔥 SMOKE TEST

# NACHHER (Full Import):
limit = 10000  # ✅ COQL max per call
# Remove max_pages variable and check
```

---

## 🐛 Troubleshooting

### Problem: "Module Invoices not found"
**Lösung:** Check in Zoho CRM ob das Modul verfügbar ist
```bash
# Zoho CRM → Setup → Modules → Check "Invoices" aktiv
```

### Problem: "REST API returns empty"
**Lösung:** Check Zoho OAuth Scopes
```
Required Scopes:
- ZohoCRM.modules.invoices.READ
- ZohoCRM.modules.subscriptions.READ
- ZohoCRM.modules.emails.READ

Or simply: ZohoCRM.modules.ALL
```

### Problem: "Field Account_Name not found"
**Lösung:** Field-Namen können variieren
```python
# Check with /crm/v6/settings/fields?module=Invoices
# Adjust fields list accordingly
```

---

## ✅ Success Criteria

Smoke Test erfolgreich wenn:

- [ ] **Invoices importiert** (~50 nodes)
- [ ] **Subscriptions importiert** (~50 nodes)
- [ ] **Emails importiert** (~50 nodes)
- [ ] **HAS_INVOICE Relationships** existieren
- [ ] **HAS_SUBSCRIPTION Relationships** existieren
- [ ] **HAS_EMAIL Relationships** existieren
- [ ] **Logs sauber** (keine REST API Errors)
- [ ] **Properties vollständig** (grand_total, status, etc.)

---

## 📝 Known Limitations

### 1. REST API Rate Limits
- Max 200 records per call
- Pagination required for > 200 records
- Same rate limit as COQL (100 calls/min)

### 2. Field Name Variations
- Zoho Feldnamen können je nach Setup variieren
- Current config basiert auf Standard Zoho Setup
- Ggf. Anpassung nötig für Custom Fields

### 3. Smoke Test Limitation
- Nur 50 Records pro Modul
- Full Import needed für vollständige Daten

---

**Status:** ✅ Ready for Deployment  
**Impact:** HIGH - Adds critical Finance & Communication data  
**Next:** Deploy → Clear DB → Re-Sync (with new modules) → Validate → Full Import

