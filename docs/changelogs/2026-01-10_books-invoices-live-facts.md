# Zoho Books Invoices Live Facts Integration

**Datum:** 2026-01-10  
**Typ:** ✨ Feature Enhancement  
**Betrifft:** `queries.py`, `provider.py`, `query_service.py`

## Problem

User fragt nach Rechnungen → System findet nichts!

```
User: "Welche Rechnungen hat Lumix Solutions bekommen?"

Log:
  ✅ Selected: ['knowledge_base', 'zoho_books'] (confidence: 0.95)
  📞 knowledge_base: Calling tool 'search_knowledge_base'
  📞 zoho_books: ❌ KEIN TOOL GECALLT!

Response: "Keine Rechnungen gefunden."
```

**Warum?**
1. **Source `zoho_books` hat kein Tool** → Keine Live-Daten
2. **Graph Query findet BooksInvoice nicht** → Sucht nur in `name` Properties
3. **BooksInvoice Nodes haben invoice_number als name** → "INV-00123" matched nicht "Rechnung"

## Lösung

### 1. CRM Tool um Books Invoices erweitert (Option 3)

**Neue Funktion:** `query_books_invoices()` in `queries.py`

```python
async def query_books_invoices(books_client, crm_account_id: str) -> str:
    """
    Queries Zoho Books Invoices for a CRM Account.
    
    - Builds customer mapping (Books customer_id → CRM account_id)
    - Fetches invoices from Books API
    - Filters by CRM Account
    - Returns formatted Markdown with status, totals, balance
    """
```

**Output Format:**
```markdown
### 🧾 Rechnungen (Zoho Books)

- ✅ **INV-000123**: EUR 5,000.00 (Balance: 0.00) | paid | Date: 2024-12-01 | Due: 2024-12-31
- 📤 **INV-000124**: EUR 2,500.00 (Balance: 2,500.00) | sent | Date: 2025-01-05 | Due: 2025-01-20
- ⚠️ **INV-000125**: EUR 1,200.00 (Balance: 1,200.00) | overdue | Date: 2024-11-01 | Due: 2024-11-30

**Total**: EUR 8,700.00
**Outstanding Balance**: EUR 3,700.00
**Total Invoices**: 3
```

**Status Emojis:**
- ✅ `paid` - Bezahlt
- 📤 `sent` - Versendet
- 📝 `draft` - Entwurf
- ⚠️ `overdue` - Überfällig
- ❌ `void` - Storniert

### 2. Provider erweitert um Books Client zu übergeben

**`provider.py` (Zeilen 318-336):**
```python
async def search_live_facts(self, entity_id: str, query_context: str) -> str:
    """Includes Books Invoices if Books integration is enabled."""
    return await execute_live_facts_query(
        self.client, 
        entity_id, 
        query_context,
        books_client=self.books_client  # ✅ Pass Books client
    )
```

**`queries.py` - Signatur updated:**
```python
async def search_live_facts(
    client: ZohoClient, 
    entity_id: str, 
    query_context: str,
    books_client = None  # ✅ Optional Books client
) -> str:
```

### 3. Graph Query um Invoice-Erkennung erweitert

**Intelligente Keyword-Erkennung:**
```python
# Erkennt Invoice-bezogene Anfragen
invoice_keywords = any(
    kw.lower() in ['rechnung', 'rechnungen', 'invoice', 'invoices', 'faktura']
    for kw in keywords
)
```

**Bei Invoice-Keywords:** Sucht auch nach `BooksInvoice` Nodes!
```cypher
// Zusätzliche Suche nach BooksInvoices
OPTIONAL MATCH (n)<-[:HAS_INVOICE]-(invoice:BooksInvoice)
RETURN 
  ...,
  invoice.invoice_number,
  invoice.status,
  invoice.total,
  invoice.balance
```

## Geänderte Dateien

### 1. `backend/app/integrations/zoho/queries.py`

**Neue Funktion: `query_books_invoices()` (Zeilen ~182-250):**
- Fetcht Books Invoices über Books API
- Verwendet Customer Mapping (books_customer_id → crm_account_id)
- Formatiert als Markdown mit Status, Beträgen, Saldo
- Gruppiert nach CRM Account

**Updated: `search_live_facts()` (Zeile ~253):**
- Neuer Parameter: `books_client` (optional)
- Ruft `query_books_invoices()` auf wenn verfügbar
- Integriert Invoice-Daten in Live Facts

### 2. `backend/app/integrations/zoho/provider.py`

**Updated: `search_live_facts()` (Zeilen 318-336):**
```python
return await execute_live_facts_query(
    self.client, 
    entity_id, 
    query_context,
    books_client=self.books_client  # Pass Books client
)
```

### 3. `backend/app/services/graph_operations/query_service.py`

**Updated: `_search_by_keywords()` (Zeilen 278-419):**
- Erkennt Invoice-Keywords automatisch
- Erweiterte Query für Invoice-Suche
- Fetcht auch `BooksInvoice` Nodes wenn relevant

```python
if invoice_keywords:
    logger.debug("💡 Invoice keywords detected - including BooksInvoice search")
    # Extended query with BooksInvoice matching
```

## Erwartetes Verhalten

### Vorher (❌)

```
User: "Welche Rechnungen hat Lumix Solutions bekommen?"

System:
  - Graph Query findet nichts (sucht nur in "name")
  - Keine Live Facts (kein Books Tool)
  
Response: "Keine Rechnungen gefunden."
```

### Nachher (✅)

```
User: "Welche Rechnungen hat Lumix Solutions bekommen?"

Log:
  🤖 LLM extracting keywords: ["Lumix Solutions", "Rechnungen"]
  💡 Invoice keywords detected - including BooksInvoice search
  
  CRM Tool:
    🔍 Searching live facts...
    📊 Fetching Books Invoices for CRM Account: 506156000032560038
    ✅ Found 3 Books Invoices

Response:
  ### 🧾 Rechnungen (Zoho Books)

  - ✅ INV-000123: EUR 5,000.00 | paid | Date: 2024-12-01
  - 📤 INV-000124: EUR 2,500.00 | sent | Date: 2025-01-05
  - ⚠️ INV-000125: EUR 1,200.00 | overdue | Date: 2024-11-01

  Total: EUR 8,700.00
  Outstanding Balance: EUR 3,700.00
```

## Funktionsweise

### 1. Source Discovery wählt `zoho_books`
```python
LLM Reasoning: "User fragt nach Rechnungen von Kunde"
Selected: ['knowledge_base', 'zoho_books']  # ✅
```

### 2. CRM Tool wird gecallt
```python
get_crm_facts(entity_id='zoho_506156000032560038')
  → provider.search_live_facts(...)
    → queries.search_live_facts(..., books_client=books_client)  # ✅
      → query_books_invoices(books_client, crm_account_id)  # ✅
```

### 3. Books API wird abgefragt
```python
# Step 1: Customer Mapping
customer_mapping = await books_client.build_customer_to_account_mapping()
# → {books_customer_id: crm_account_id}

# Step 2: Reverse lookup
reverse_mapping = {v: k for k, v in customer_mapping.items()}
books_customer_id = reverse_mapping.get(crm_account_id)

# Step 3: Fetch & Filter Invoices
invoices = await books_client.fetch_all_invoices(max_pages=5)
customer_invoices = [inv for inv in invoices if inv['customer_id'] == books_customer_id]
```

### 4. Formatierung & Output
```python
# Status Emojis
status_emoji = {
    "paid": "✅",
    "sent": "📤",
    "overdue": "⚠️"
}

# Formatted Output
"- {emoji} **{invoice_number}**: {currency} {total} | {status} | Date: {date}"
```

## Testing

**Manuelle Tests:**
1. ✅ "Welche Rechnungen hat Lumix Solutions bekommen?"
2. ✅ "Zeig mir alle Invoices von ACME Corp"
3. ✅ "Was ist der offene Rechnungssaldo von Kunde X?"
4. ✅ "Gibt es überfällige Rechnungen?"

**Graph Query Test:**
```
User: "Rechnungen Lumix"

Log:
  🤖 LLM extracted keywords: ["Rechnungen", "Lumix"]
  💡 Invoice keywords detected - including BooksInvoice search
  
Cypher Query:
  MATCH (n) WHERE ... CONTAINS "Lumix"
  OPTIONAL MATCH (n)<-[:HAS_INVOICE]-(invoice:BooksInvoice)
  RETURN ... invoice.invoice_number, invoice.status, ...
```

## Migration / Rollout

✅ **Keine Breaking Changes**
- Backwards-kompatibel
- Books Client optional
- Fallback wenn Books nicht konfiguriert

**Voraussetzungen:**
1. `ZOHO_BOOKS_ORGANIZATION_ID` muss konfiguriert sein
2. Books Customer müssen mit CRM Accounts verknüpft sein (`zcrm_account_id`)
3. Full CRM Sync muss durchgelaufen sein

**Empfohlene Schritte:**
1. Deploy Code
2. Testen mit Account der Books Invoices hat
3. Monitoring auf Books API Calls

## Performance

**Books API Calls:**
- 1x Customer Mapping (~200ms)
- 1x Invoice List (~500ms)
- Total: ~700ms zusätzlich pro Invoice-Anfrage

**Caching-Potential (Future):**
- Customer Mapping könnte gecacht werden (ändert sich selten)
- Invoice Liste könnte periodisch gefetcht werden

## Hinweise

- **Live Facts vs. Graph:** 
  - Graph hat nur Metadaten (invoice_number, date)
  - Live Facts haben aktuellen Status, Balance, etc.
  
- **Invoice-Keywords:**
  - "Rechnung", "Rechnungen", "Invoice", "Invoices", "Faktura"
  - Case-insensitive
  - Triggert erweiterte Graph-Suche

- **Customer Mapping:**
  - Verwendet `zcrm_account_id` aus Books Customer API
  - Siehe [2026-01-10_books-invoice-mapping-fix.md](./2026-01-10_books-invoice-mapping-fix.md)

## Siehe auch

- [2026-01-10_books-invoice-mapping-fix.md](./2026-01-10_books-invoice-mapping-fix.md) - Invoice Mapping Fix
- [2026-01-10_llm-query-generation.md](./2026-01-10_llm-query-generation.md) - LLM Query Generation
- [GRAPH_SCHEMA.md](../GRAPH_SCHEMA.md) - Graph Schema

---

**Status:** ✅ Implementiert  
**Autor:** Michael Schiestl  
**Review:** Pending

