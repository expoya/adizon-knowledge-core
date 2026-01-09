# Zoho Books Integration - Setup Guide

## ✅ Was wurde implementiert

**Vollständige Zoho Books/Billing Integration:**
- ✅ Invoices (Rechnungen) aus Zoho Books
- ✅ Subscriptions (Abonnements) aus Zoho Books/Billing
- ✅ Automatische Pagination
- ✅ Rate Limiting
- ✅ Graph Integration (HAS_INVOICE, HAS_SUBSCRIPTION Relations)

---

## 🎯 Was du jetzt tun musst

### Schritt 1: Multi-Service OAuth Token generieren

**Aktueller Token (nur CRM):**
```
ZohoCRM.modules.ALL
ZohoCRM.modules.emails.ALL
ZohoCRM.users.READ
ZohoCRM.settings.ALL
ZohoCRM.coql.READ
```

**NEUER Token (CRM + Books):**
```
ZohoCRM.modules.ALL,ZohoCRM.modules.emails.ALL,ZohoCRM.users.READ,ZohoCRM.settings.ALL,ZohoCRM.coql.READ,ZohoBooks.fullaccess.all
```

#### 1.1 Authorization URL bauen
```
https://accounts.zoho.eu/oauth/v2/auth?scope=ZohoCRM.modules.ALL,ZohoCRM.modules.emails.ALL,ZohoCRM.users.READ,ZohoCRM.settings.ALL,ZohoCRM.coql.READ,ZohoBooks.fullaccess.all&client_id=YOUR_CLIENT_ID&response_type=code&access_type=offline&redirect_uri=YOUR_REDIRECT_URI
```

**Ersetze:**
- `YOUR_CLIENT_ID` → Deine Client ID (gleiche wie für CRM!)
- `YOUR_REDIRECT_URI` → Deine Redirect URI

#### 1.2 Authorization Code holen
1. URL im Browser öffnen
2. Bei Zoho einloggen
3. **WICHTIG:** Permissions für CRM UND Books werden angezeigt!
4. Akzeptieren
5. Authorization Code aus URL kopieren

#### 1.3 Refresh Token generieren
```bash
curl -X POST 'https://accounts.zoho.eu/oauth/v2/token' \
  -d 'grant_type=authorization_code' \
  -d 'client_id=YOUR_CLIENT_ID' \
  -d 'client_secret=YOUR_CLIENT_SECRET' \
  -d 'redirect_uri=YOUR_REDIRECT_URI' \
  -d 'code=YOUR_AUTHORIZATION_CODE'
```

**Response:**
```json
{
  "access_token": "...",
  "refresh_token": "1000.xxx...",
  "scope": "ZohoCRM... ZohoBooks.fullaccess.all",
  "api_domain": "https://www.zohoapis.eu",
  "expires_in": 3600
}
```

**Kopiere `refresh_token`!**

---

### Schritt 2: organization_id ermitteln

#### Option A: Aus Zoho Books URL
1. Zoho Books einloggen: https://books.zoho.eu
2. URL anschauen:
   ```
   https://books.zoho.eu/app/...?organization_id=123456789
   ```
3. `123456789` ist deine organization_id

#### Option B: Via API
```bash
# 1. Access Token holen
curl -X POST 'https://accounts.zoho.eu/oauth/v2/token' \
  -d 'grant_type=refresh_token' \
  -d 'client_id=YOUR_CLIENT_ID' \
  -d 'client_secret=YOUR_CLIENT_SECRET' \
  -d 'refresh_token=YOUR_NEW_REFRESH_TOKEN'

# 2. Organizations abrufen
curl -X GET 'https://www.zohoapis.eu/books/v3/organizations' \
  -H 'Authorization: Zoho-oauthtoken YOUR_ACCESS_TOKEN'
```

**Response:**
```json
{
  "organizations": [
    {
      "organization_id": "123456789",
      "name": "Voltage GmbH",
      ...
    }
  ]
}
```

**Kopiere `organization_id`!**

---

### Schritt 3: Railway Environment Variables setzen

```bash
# EXISTING (ersetzen!)
ZOHO_REFRESH_TOKEN=1000.xxx...  # ← NEUER Multi-Service Token!

# NEW (hinzufügen!)
ZOHO_BOOKS_ORGANIZATION_ID=123456789
```

**Wo?**
1. Railway Dashboard → Dein Service
2. **Variables** Tab
3. Edit `ZOHO_REFRESH_TOKEN` → Neuer Token
4. Add `ZOHO_BOOKS_ORGANIZATION_ID` → organization_id

**Save** → Railway macht automatisch Redeploy!

---

### Schritt 4: Testen!

#### 4.1 Deployment abwarten
Railway deployt automatisch nach Env-Variable-Änderung.

#### 4.2 CRM Sync triggern
```bash
POST /api/v1/crm-sync
{}
```

#### 4.3 Erwartete Logs

**✅ SUCCESS:**
```
✅ Zoho Books integration enabled (org_id: 123456789)
...
📋 Processing BooksInvoices (module: BooksInvoices, label: Invoice)...
    🔄 Fetching Books Invoices (max 1 pages)...
    📄 Page 1: Fetched 150 invoices (Total: 150)
    ✅ Total Books Invoices fetched: 150
    ✅ Processed 150 BooksInvoices

📋 Processing BooksSubscriptions (module: BooksSubscriptions, label: Subscription)...
    🔄 Fetching Books Subscriptions (max 1 pages)...
    📄 Page 1: Fetched 25 subscriptions (Total: 25)
    ✅ Total Books Subscriptions fetched: 25
    ✅ Processed 25 BooksSubscriptions
```

**⚠️ Falls organization_id fehlt:**
```
⚠️ Books module 'BooksInvoices' requested but ZOHO_BOOKS_ORGANIZATION_ID not configured
```

**❌ Falls Token-Scope fehlt:**
```
❌ REST API failed for BooksInvoices | Error: 401 - Unauthorized
```
→ Neuen Token mit `ZohoBooks.fullaccess.all` generieren!

---

## 📊 Response

**Erwartete Response:**
```json
{
  "status": "success",
  "entities_synced": 642,
  "entity_types": [
    "User", "Lead", "Account", "Contact", "Deal",
    "Task", "Note", "CalendlyEvent", "Einwand", "Attachment",
    "Invoice",           // CRM Invoice (simple)
    "Invoice",           // Books Invoice (professional) ← DUPLICATE LABEL!
    "Subscription"       // Books Subscription
  ],
  "message": "CRM Sync completed successfully: 642 entities synced"
}
```

**Hinweis:** "Invoice" erscheint 2x (CRM + Books), haben aber unterschiedliche `source_id`:
- CRM: `zoho_506156000001234567`
- Books: `zoho_books_invoice_987654321`

---

## 🔍 Neo4j Validierung

### Query 1: Invoices zählen
```cypher
MATCH (i:Invoice)
RETURN 
  CASE 
    WHEN i.source_id STARTS WITH 'zoho_books_invoice_' THEN 'Books Invoice'
    ELSE 'CRM Invoice'
  END AS type,
  count(*) AS count
```

**Erwartung:**
```
Books Invoice  | 150
CRM Invoice    | 1
```

### Query 2: Subscriptions prüfen
```cypher
MATCH (s:Subscription)
RETURN s.name, s.status, s.amount, s.customer_name
LIMIT 10
```

### Query 3: Relations prüfen
```cypher
MATCH (a:Account)-[:HAS_INVOICE]->(i:Invoice)
WHERE i.source_id STARTS WITH 'zoho_books_invoice_'
RETURN a.name AS account, count(i) AS invoices
ORDER BY invoices DESC
LIMIT 10
```

---

## 📚 Technische Details

### Books API Endpoints
```
GET /books/v3/invoices
  ?organization_id=123456789
  &page=1
  &per_page=200

GET /books/v3/subscriptions
  ?organization_id=123456789
  &page=1
  &per_page=200

# Fallback für Subscriptions:
GET /billing/v1/subscriptions
  ?organization_id=123456789
  &page=1
  &per_page=200
```

### Field Mapping

**Invoices:**
- `invoice_id` → `zoho_books_id`
- `invoice_number` → `invoice_number`, `name`
- `customer_name` → `customer_name`
- `customer_id` → `customer_id` (for relations)
- `total` → `total`
- `status` → `status`
- `date` → `date`

**Subscriptions:**
- `subscription_id` → `zoho_books_id`
- `subscription_number` / `name` → `subscription_number`, `name`
- `customer_name` → `customer_name`
- `customer_id` → `customer_id` (for relations)
- `amount` / `sub_total` → `amount`
- `status` → `status`
- `start_date`, `end_date` → `start_date`, `end_date`

### Graph Relations
```cypher
// Invoices
(Account)-[:HAS_INVOICE]->(Invoice)

// Subscriptions
(Account)-[:HAS_SUBSCRIPTION]->(Subscription)
```

**Hinweis:** Relations basieren auf `customer_id` Match zwischen Books und CRM Accounts.

---

## ⚠️ Bekannte Limitierungen

### 1. Customer Matching
Books `customer_id` ≠ CRM Account `id` in den meisten Fällen!

**Problem:** Books Customers und CRM Accounts sind separate Entities.

**Lösung (später):**
- Matching via `customer_name` oder Email
- Oder: Separate "Customer" Nodes erstellen

### 2. Smoke Test Modus
Aktuell: `max_pages=1` → Nur ~200 Invoices/Subscriptions

**Nächster Schritt:** Auf `max_pages=100` hochdrehen für Full Import!

### 3. Rate Limiting
Zoho Books API: 100 calls/min

**Aktuell:** 0.6s Sleep zwischen Calls (safe)

---

## ✅ Checkliste

### Token Setup
- [ ] Multi-Service Token generiert (`ZohoBooks.fullaccess.all` im Scope)
- [ ] Token in Response enthält "ZohoBooks" im Scope
- [ ] Railway `ZOHO_REFRESH_TOKEN` updated

### Organization ID
- [ ] organization_id aus Zoho Books UI oder API ermittelt
- [ ] Railway `ZOHO_BOOKS_ORGANIZATION_ID` gesetzt

### Testing
- [ ] Railway Deployment erfolgreich
- [ ] CRM Sync zeigt "Zoho Books integration enabled"
- [ ] BooksInvoices werden importiert
- [ ] BooksSubscriptions werden importiert
- [ ] Neo4j enthält Books Invoices mit `source_id: zoho_books_invoice_*`

---

## 🎯 Nächste Schritte nach erfolgreichem Test

1. **Smoke Test validieren:** 50 Records pro Modul
2. **LIMIT hochdrehen:** Von 50 auf 10000
3. **Full Import:** Alle 30.000+ Entities
4. **Customer Matching:** Books Customers mit CRM Accounts verknüpfen
5. **Emails Phase 3:** Related Lists Implementation

---

**Bereit?** Token + organization_id in Railway setzen und testen! 🚀

