# 🕸️ Graph Schema Documentation

## Übersicht

Das Adizon Knowledge Core System nutzt Neo4j als Knowledge Graph mit einem **typisiertem Schema**. Anstelle von generischen `CRMEntity` Nodes verwendet das System spezifische Labels für verschiedene Geschäftsobjekte, was bessere Queries und klare Datenmodellierung ermöglicht.

---

## 📊 Node Types (Labels)

### Core Business Entities

#### 1. **User** 👤
Repräsentiert Mitarbeiter und System-Benutzer.

```cypher
(:User {
  source_id: "zoho_12345",
  name: "John Doe",
  email: "john@company.com",
  zoho_id: "12345",
  created_at: datetime(),
  synced_at: datetime(),
  source: "Zoho CRM"
})
```

#### 2. **Account** 🏢
Firmen und Organisationen (Kunden, Partner).

```cypher
(:Account {
  source_id: "zoho_67890",
  name: "Voltage Solutions GmbH",
  zoho_id: "67890",
  owner: "...",
  created_at: datetime(),
  synced_at: datetime()
})
```

#### 3. **Contact** 👥
Kontaktpersonen innerhalb von Accounts.

```cypher
(:Contact {
  source_id: "zoho_11111",
  name: "Jane Smith",
  email: "jane@voltage.de",
  zoho_id: "11111",
  created_at: datetime()
})
```

#### 4. **Lead** 🎯
Potenzielle Kunden (noch nicht konvertiert).

```cypher
(:Lead {
  source_id: "zoho_22222",
  name: "Bob Miller",
  company: "TechCorp",
  email: "bob@techcorp.com",
  zoho_id: "22222",
  created_at: datetime()
})
```

#### 5. **Deal** 💰
Verkaufschancen und Geschäfte.

```cypher
(:Deal {
  source_id: "zoho_33333",
  name: "Q1 2026 Deal",
  amount: 50000.00,
  stage: "Negotiation",
  closing_date: "2026-03-31",
  zoho_id: "33333",
  created_at: datetime()
})
```

---

### Activity & Interaction Entities

#### 6. **CalendlyEvent** 📅
Meeting und Event-Buchungen (via Calendly Integration).

```cypher
(:CalendlyEvent {
  source_id: "zoho_44444",
  name: "Discovery Call",
  calendlyforzohocrm__status: "scheduled",
  calendlyforzohocrm__start_time: "2026-01-15T14:00:00Z",
  zoho_id: "44444"
})
```

#### 7. **Task** ✅
Aufgaben und To-Dos.

```cypher
(:Task {
  source_id: "zoho_55555",
  subject: "Follow-up Call",
  status: "In Progress",
  zoho_id: "55555"
})
```

#### 8. **Note** 📝
Notizen zu Kontakten, Deals, etc.

```cypher
(:Note {
  source_id: "zoho_66666",
  name: "Meeting Notes",
  note_content: "Discussed pricing...",
  zoho_id: "66666"
})
```

---

### Sales & Finance Entities

#### 9. **BooksInvoice** 🧾
Rechnungen aus Zoho Books (professionelles Buchhaltungssystem).

**Hinweis:** Das alte CRM "Invoices" Modul (nur 1 Testdatensatz) wird nicht mehr importiert.

```cypher
(:BooksInvoice {
  source_id: "zoho_books_invoice_123456",
  name: "INV-2026-001",
  invoice_number: "INV-2026-001",
  total: 5000.00,
  status: "paid",
  customer_name: "ACME Corp",
  zoho_books_id: "123456"
})
```

#### 10. **Subscription** 🔄
Abonnements und wiederkehrende Zahlungen.

```cypher
(:Subscription {
  source_id: "zoho_88888",
  name: "Enterprise Plan",
  total: 999.00,
  status: "Active",
  zoho_id: "88888"
})
```

#### 11. **Einwand** 🛡️
Einwände im Verkaufsprozess.

```cypher
(:Einwand {
  source_id: "zoho_99999",
  name: "Price Objection",
  grund: "Budget concerns",
  status: "Resolved",
  zoho_id: "99999"
})
```

#### 12. **Attachment** 📎
Dokumente und Dateien.

```cypher
(:Attachment {
  source_id: "zoho_00000",
  file_name: "proposal.pdf",
  zoho_id: "00000"
})
```

---

## 🔗 Relationship Types (Edges)

### Ownership & Assignment

#### HAS_OWNER
Verknüpft Entities mit ihren Besitzern (Users).

```cypher
(:Account)-[:HAS_OWNER]->(:User)
(:Lead)-[:HAS_OWNER]->(:User)
(:Deal)-[:HAS_OWNER]->(:User)
(:Contact)-[:HAS_OWNER]->(:User)
```

**Direction:** `OUTGOING` (Entity → User)

---

### Organizational Structure

#### WORKS_AT
Kontakte arbeiten bei Accounts.

```cypher
(:Contact)-[:WORKS_AT]->(:Account)
```

**Direction:** `OUTGOING` (Contact → Account)

#### PARENT_OF
Account-Hierarchien.

```cypher
(:Account {name: "Parent Corp"})-[:PARENT_OF]->(:Account {name: "Subsidiary"})
```

**Direction:** `INCOMING` (Parent ← Child im Schema)

---

### Sales Process

#### HAS_DEAL
Accounts haben Deals.

```cypher
(:Account)-[:HAS_DEAL]->(:Deal)
```

**Direction:** `INCOMING` (Account ← Deal im Schema, aber Query: Account → Deal)

#### ASSOCIATED_WITH
Deals sind mit Contacts verbunden.

```cypher
(:Deal)-[:ASSOCIATED_WITH]->(:Contact)
```

**Direction:** `OUTGOING` (Deal → Contact)

#### IS_CONVERTED_FROM
Konvertierte Leads → Accounts.

```cypher
(:Account)-[:IS_CONVERTED_FROM]->(:Lead)
```

**Direction:** `INCOMING` (Account ← Lead im Schema)

---

### Activities & Interactions

#### HAS_EVENT
Meetings und Events.

```cypher
(:Lead)-[:HAS_EVENT]->(:CalendlyEvent)
(:Contact)-[:HAS_EVENT]->(:CalendlyEvent)
(:Account)-[:HAS_EVENT]->(:CalendlyEvent)
```

**Direction:** `INCOMING` im Schema, aber logisch: Entity hat Event

#### HAS_TASK
Aufgaben zu Entities (polymorph).

```cypher
(:Lead)-[:HAS_TASK]->(:Task)
(:Account)-[:HAS_TASK]->(:Task)
(:CRMEntity)-[:HAS_TASK]->(:Task)  // Fallback für unbekannte Typen
```

**Direction:** `INCOMING`

#### HAS_NOTE
Notizen zu Entities.

```cypher
(:Deal)-[:HAS_NOTE]->(:Note)
(:Contact)-[:HAS_NOTE]->(:Note)
```

**Direction:** `INCOMING`

#### HAS_OBJECTION
Einwände bei Leads.

```cypher
(:Lead)-[:HAS_OBJECTION]->(:Einwand)
```

**Direction:** `INCOMING`

---

### Finance

#### HAS_INVOICE
Rechnungen zu Accounts (via Zoho Books zcrm_account_id Mapping).

```cypher
(:Account)-[:HAS_INVOICE]->(:BooksInvoice)
```

**Direction:** `INCOMING`

**Hinweis:** Die Verknüpfung erfolgt über das `zcrm_account_id` Feld aus Zoho Books Contacts (Customers), welches auf die CRM Account ID verweist.

#### HAS_SUBSCRIPTION
Abonnements zu Accounts.

```cypher
(:Account)-[:HAS_SUBSCRIPTION]->(:Subscription)
```

**Direction:** `INCOMING`

---

### Documents

#### HAS_DOCUMENTS
Dokumente/Attachments (polymorph).

```cypher
(:Deal)-[:HAS_DOCUMENTS]->(:Attachment)
(:Account)-[:HAS_DOCUMENTS]->(:Attachment)
```

**Direction:** `INCOMING`

---

## 🏗️ Graph Architecture

### Entity Structure

```
┌─────────────────────────────────────────────────────────────┐
│                         User (Owner)                        │
│                    john@company.com                         │
└────────────┬──────────────────────────────┬─────────────────┘
             │ HAS_OWNER                    │ HAS_OWNER
             ↓                              ↓
    ┌────────────────┐            ┌────────────────────┐
    │    Account     │            │       Lead         │
    │ Voltage GmbH   │            │   Bob Miller       │
    └────┬────┬──────┘            └──────┬─────┬───────┘
         │    │                          │     │
         │    │ HAS_DEAL                 │     │ HAS_EVENT
         │    ↓                          │     ↓
         │  ┌──────────┐                │  ┌──────────────┐
         │  │   Deal   │                │  │ CalendlyEvent│
         │  │ Q1 Deal  │                │  │Discovery Call│
         │  │ €50k     │                │  └──────────────┘
         │  └──────────┘                │
         │                               │ HAS_OBJECTION
         │ WORKS_AT                     ↓
         │                       ┌──────────────┐
         ↓                       │   Einwand    │
    ┌──────────┐                │Price Concern │
    │ Contact  │                └──────────────┘
    │Jane Smith│
    └──────────┘
```

---

## 📝 Cypher Query Examples

### 1. Find All Deals for an Account

```cypher
MATCH (a:Account {name: "Voltage Solutions GmbH"})-[:HAS_DEAL]->(d:Deal)
RETURN d.name AS deal_name, 
       d.amount AS amount, 
       d.stage AS stage
ORDER BY d.amount DESC
```

### 2. Get Owner's Portfolio

```cypher
MATCH (u:User {name: "John Doe"})-[:HAS_OWNER]->(entity)
RETURN labels(entity)[0] AS entity_type,
       entity.name AS name,
       count(*) AS count
```

### 3. Contact Network & Deals

```cypher
MATCH (c:Contact)-[:WORKS_AT]->(a:Account)-[:HAS_DEAL]->(d:Deal)
WHERE c.name CONTAINS "Jane"
RETURN c.name AS contact,
       a.name AS company,
       collect(d.name) AS deals,
       sum(d.amount) AS total_value
```

### 4. Event Timeline for Lead

```cypher
MATCH (l:Lead {name: "Bob Miller"})-[:HAS_EVENT]->(e:CalendlyEvent)
RETURN e.name AS event,
       e.calendlyforzohocrm__start_time AS scheduled,
       e.calendlyforzohocrm__status AS status
ORDER BY e.calendlyforzohocrm__start_time DESC
```

### 5. Account with All Related Data

```cypher
MATCH (a:Account {name: "Voltage Solutions GmbH"})
OPTIONAL MATCH (a)-[:HAS_DEAL]->(d:Deal)
OPTIONAL MATCH (a)-[:HAS_INVOICE]->(inv:Invoice)
OPTIONAL MATCH (a)-[:HAS_SUBSCRIPTION]->(sub:Subscription)
OPTIONAL MATCH (c:Contact)-[:WORKS_AT]->(a)
RETURN a.name AS account,
       collect(DISTINCT d.name) AS deals,
       collect(DISTINCT c.name) AS contacts,
       collect(DISTINCT inv.name) AS invoices,
       collect(DISTINCT sub.name) AS subscriptions
```

### 6. Lead Conversion Tracking

```cypher
MATCH (a:Account)-[:IS_CONVERTED_FROM]->(l:Lead)
RETURN a.name AS account,
       l.name AS original_lead,
       l.company AS lead_company
```

### 7. Find Unresolved Objections

```cypher
MATCH (l:Lead)-[:HAS_OBJECTION]->(e:Einwand)
WHERE e.status <> "Resolved"
RETURN l.name AS lead,
       e.name AS objection,
       e.grund AS reason,
       e.status AS status
```

### 8. Account Hierarchy

```cypher
MATCH path = (parent:Account)-[:PARENT_OF*]->(child:Account)
WHERE parent.name = "Parent Corp"
RETURN parent.name AS parent,
       [node IN nodes(path) | node.name] AS hierarchy
```

---

## 🔄 Data Flow & Synchronization

### Sync Process (3 Steps)

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Fetch from Zoho CRM                                │
│   • COQL Queries per Module                                │
│   • User API for Users                                     │
│   • Extract: source_id, label, properties, relations       │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Batch Node Creation (Group by Label)               │
│   • UNWIND $batch MERGE (n:Label {source_id: ...})        │
│   • Set properties (name, email, amount, etc.)            │
│   • Track created vs updated                              │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Batch Relationship Creation (Group by Edge Type)   │
│   • Separate OUTGOING vs INCOMING                          │
│   • MERGE relationships with direction                     │
│   • Create stub nodes for missing targets                  │
└─────────────────────────────────────────────────────────────┘
```

### API Endpoint

```bash
POST /api/v1/ingestion/crm-sync
Content-Type: application/json

{
  "entity_types": ["Accounts", "Leads", "Deals", "Contacts"]
}
```

**Response:**
```json
{
  "status": "success",
  "entities_synced": 350,
  "entities_created": 120,
  "entities_updated": 230,
  "entity_types": ["Account", "Lead", "Deal", "Contact", "User"],
  "message": "Successfully synced 350 entities from Zoho CRM",
  "errors": []
}
```

---

## 🛠️ Technical Implementation

### Provider: SCHEMA_MAPPING

```python
SCHEMA_MAPPING = {
    "Accounts": {
        "label": "Account",
        "module_name": "Accounts",
        "fields": ["id", "Account_Name", "Owner", "Parent_Account"],
        "relations": [
            {
                "field": "Owner",
                "edge": "HAS_OWNER",
                "target_label": "User",
                "direction": "OUTGOING"
            },
            {
                "field": "Parent_Account",
                "edge": "PARENT_OF",
                "target_label": "Account",
                "direction": "INCOMING"
            }
        ]
    },
    # ... weitere 10 Typen
}
```

### Return Structure

```python
{
    "source_id": "zoho_67890",
    "label": "Account",
    "properties": {
        "name": "Voltage Solutions GmbH",
        "zoho_id": "67890",
        "owner": "..."
    },
    "relations": [
        {
            "target_id": "zoho_12345",
            "edge_type": "HAS_OWNER",
            "target_label": "User",
            "direction": "OUTGOING"
        }
    ]
}
```

---

## 🎯 Best Practices

### 1. Query Performance

✅ **DO:** Use specific labels
```cypher
MATCH (a:Account)  // Fast - uses label index
WHERE a.name = "Acme"
RETURN a
```

❌ **DON'T:** Query without labels
```cypher
MATCH (n)  // Slow - scans all nodes
WHERE n.name = "Acme"
RETURN n
```

### 2. Relationship Direction

✅ **DO:** Follow the natural relationship direction
```cypher
// Natural: Contact works at Account
MATCH (c:Contact)-[:WORKS_AT]->(a:Account)
```

❌ **DON'T:** Query against the direction
```cypher
// Unnatural: Account has Contact
MATCH (a:Account)<-[:WORKS_AT]-(c:Contact)
```

### 3. Index Usage

Create indexes for frequently queried properties:
```cypher
CREATE INDEX account_name IF NOT EXISTS FOR (a:Account) ON (a.name);
CREATE INDEX deal_amount IF NOT EXISTS FOR (d:Deal) ON (d.amount);
CREATE INDEX source_id IF NOT EXISTS FOR (n) ON (n.source_id);
```

---

## 🔧 Migration Guide

### From Old Schema (CRMEntity) to New Schema

#### Before:
```cypher
(:CRMEntity {type: "Account", name: "Acme"})
(:CRMEntity {type: "Deal", name: "Q1 Deal"})
```

#### After:
```cypher
(:Account {name: "Acme"})
(:Deal {name: "Q1 Deal"})
```

### Cleanup Old Nodes (Optional)

```cypher
// Find old CRMEntity nodes
MATCH (n:CRMEntity)
WHERE NOT EXISTS(n.source_id)  // Old format
RETURN count(n);

// Optional: Delete old nodes (BE CAREFUL!)
// MATCH (n:CRMEntity)
// WHERE NOT EXISTS(n.source_id)
// DETACH DELETE n;
```

### Verify New Schema

```cypher
// Count nodes by label
CALL db.labels() YIELD label
CALL apoc.cypher.run(
  "MATCH (n:" + label + ") RETURN count(n) AS count", 
  {}
) YIELD value
RETURN label, value.count AS count
ORDER BY count DESC;
```

---

## 📊 Statistics & Monitoring

### Node Count by Type

```cypher
MATCH (n)
RETURN labels(n)[0] AS type, count(n) AS count
ORDER BY count DESC
```

### Relationship Count by Type

```cypher
MATCH ()-[r]->()
RETURN type(r) AS relationship, count(r) AS count
ORDER BY count DESC
```

### Orphaned Nodes (No Relationships)

```cypher
MATCH (n)
WHERE NOT (n)--()
RETURN labels(n)[0] AS type, count(n) AS orphaned_count
```

### Data Freshness

```cypher
MATCH (n)
WHERE n.synced_at IS NOT NULL
RETURN labels(n)[0] AS type,
       max(n.synced_at) AS last_sync,
       duration.between(max(n.synced_at), datetime()).minutes AS minutes_ago
ORDER BY minutes_ago
```

---

## 🚀 Future Enhancements

### Planned Features

1. **Products & Quotes**
   - `:Product` nodes
   - `:Quote` nodes
   - `HAS_QUOTE`, `INCLUDES_PRODUCT` relationships

2. **Campaigns & Marketing**
   - `:Campaign` nodes
   - `PART_OF_CAMPAIGN` relationships

3. **Support & Cases**
   - `:Case`, `:Ticket` nodes
   - `HAS_CASE` relationships

4. **Time-based Relationships**
   - Properties: `valid_from`, `valid_until`
   - Historical relationship tracking

5. **Weighted Relationships**
   - Relationship strength scores
   - Interaction frequency

---

## 📚 References

- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/)
- [Graph Data Modeling Best Practices](https://neo4j.com/developer/data-modeling/)
- [Zoho CRM API Documentation](https://www.zoho.com/crm/developer/docs/api/)

---

**Last Updated:** 2026-01-10  
**Version:** 2.0.0  
**Status:** ✅ Production Ready

