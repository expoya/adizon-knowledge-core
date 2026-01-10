# Graph Quality Check Guide

Nach einem CRM-Sync solltest du die Qualität und Vollständigkeit des Knowledge Graphs überprüfen.

## 🔍 Quick Check via API

### 1. Graph Statistics Endpoint

```bash
GET /api/graph-stats
```

**Response:**
```json
{
  "total_nodes": 44000,
  "total_relationships": 26000,
  "node_labels": {
    "Account": 5000,
    "Lead": 8000,
    "Contact": 12000,
    "Deal": 3000,
    "User": 15,
    "Objection": 2000,
    "Calendly_Event": 1500,
    ...
  },
  "relationship_types": {
    "HAS_OWNER": 20000,
    "HAS_CONTACT": 12000,
    "HAS_DEAL": 3000,
    ...
  }
}
```

### 2. Health Check

```bash
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "graph_connected": true,
  "graph_stats": { ... }
}
```

## 📊 Erwartete Werte (Full Sync)

### Node Counts (ca. Werte, abhängig von deinem CRM):

| Label | Erwartete Range | Was es ist |
|-------|----------------|------------|
| **Account** | 3.000 - 10.000 | Firmen/Kunden |
| **Lead** | 5.000 - 15.000 | Potenzielle Kunden |
| **Contact** | 10.000 - 20.000 | Kontaktpersonen |
| **Deal** | 2.000 - 5.000 | Geschäftschancen |
| **User** | 5 - 50 | Zoho CRM Users |
| **Objection** | 1.000 - 5.000 | Einwände |
| **Calendly_Event** | 500 - 3.000 | Meetings |
| **BooksInvoice** | 150 - 1.000 | Books Rechnungen (echte Daten) |
| **Task** | 2.000 - 10.000 | Aufgaben |
| **Note** | 1.000 - 5.000 | Notizen |
| **Attachment** | 500 - 3.000 | Anhänge |

### Relationship Counts:

| Type | Erwartete Range | Verbindet |
|------|----------------|-----------|
| **HAS_OWNER** | ~20.000 | Alles → User |
| **HAS_CONTACT** | ~10.000 | Account → Contact |
| **HAS_DEAL** | ~3.000 | Account → Deal |
| **HAS_OBJECTION** | ~2.000 | Account/Lead → Objection |
| **HAS_MEETING** | ~1.500 | Account/Lead → Calendly_Event |
| **HAS_INVOICE** | ~2.000 | Account → Invoice |

## 🔎 Detaillierte Cypher Queries

### Query 1: Top 10 Node Types
```cypher
MATCH (n)
WITH labels(n) as node_labels
UNWIND node_labels as label
RETURN label, count(*) as count
ORDER BY count DESC
LIMIT 10
```

### Query 2: Top 10 Relationship Types
```cypher
MATCH ()-[r]->()
RETURN type(r) as rel_type, count(*) as count
ORDER BY count DESC
LIMIT 10
```

### Query 3: Nodes ohne Relationships (Orphans)
```cypher
MATCH (n)
WHERE NOT (n)--()
RETURN labels(n)[0] as label, count(*) as orphan_count
ORDER BY orphan_count DESC
```

**Erwartung:** 
- Sehr wenige Orphans (< 1% der Nodes)
- Hauptsächlich Users oder spezielle Entities

### Query 4: Accounts mit den meisten Relationships
```cypher
MATCH (a:Account)
OPTIONAL MATCH (a)-[r]-()
WITH a, count(r) as rel_count
RETURN a.name, rel_count
ORDER BY rel_count DESC
LIMIT 10
```

**Erwartung:**
- Top Accounts haben 50-200 Relationships
- Zeigt deine wichtigsten Kunden

### Query 5: Durchschnittliche Relationships pro Node Type
```cypher
MATCH (n)
OPTIONAL MATCH (n)-[r]-()
WITH labels(n)[0] as label, n, count(r) as rels
RETURN label, 
       count(n) as node_count,
       avg(rels) as avg_relationships,
       max(rels) as max_relationships
ORDER BY avg_relationships DESC
```

### Query 6: Prüfe ob Emails gefetcht wurden
```cypher
MATCH (e:Email)
RETURN count(e) as email_count
```

**Erwartung:**
- Sollte > 0 sein wenn Accounts/Contacts Emails haben
- Emails werden via Related Lists gefetcht

## ✅ Quality Checklist

Nach einem Full Sync sollte folgendes erfüllt sein:

- [ ] **Total Nodes:** > 30.000
- [ ] **Total Relationships:** > 20.000
- [ ] **Orphan Rate:** < 1%
- [ ] **Accounts vorhanden:** > 1.000
- [ ] **Leads vorhanden:** > 2.000
- [ ] **Contacts vorhanden:** > 5.000
- [ ] **Users vorhanden:** > 5
- [ ] **HAS_OWNER Relationships:** Ähnlich wie Total Nodes (fast jeder Node hat Owner)
- [ ] **HAS_CONTACT Relationships:** Ähnlich wie Contact Count
- [ ] **Keine Error Logs:** Check Railway Logs für Fehler

## 🐛 Troubleshooting

### Problem: Zu wenige Nodes

**Ursachen:**
1. COQL Limit erreicht (200 pro Page)
2. API Rate Limiting
3. Fehlende Berechtigungen

**Lösung:**
- Check Railway Logs für Errors
- Prüfe Zoho API Scopes
- Führe Sync nochmal aus (Incremental Sync)

### Problem: Zu wenige Relationships

**Ursachen:**
1. Sync wurde abgebrochen (Timeout)
2. Relationships werden noch erstellt (async)

**Lösung:**
- Warte 5-10 Minuten
- Check `/api/graph-stats` nochmal
- Relationships kommen NACH Nodes

### Problem: Viele Orphan Nodes

**Ursachen:**
1. Fehlerhafte Relationship-Creation
2. Falsche source_id Mappings

**Lösung:**
- Check Railway Logs für "Failed to create" Errors
- Führe Full Sync nochmal aus
- Prüfe schema.py Relationship Definitions

## 📈 Performance Metrics

**Erwartete Sync-Zeiten:**

- **Nodes (44k):** 3-5 Minuten
- **Relationships (26k):** 5-10 Minuten
- **Total:** 10-15 Minuten für Full Sync

**Memory Usage:**
- Backend: ~500 MB - 1 GB
- Neo4j: ~1 GB - 2 GB (abhängig von Graph-Größe)

## 🎯 Nächste Schritte

Nach erfolgreichem Quality Check:

1. **Test Chat-Endpoint:** `/api/chat`
2. **Test Graph-Queries:** Probiere Queries in Neo4j Browser
3. **Upload Documents:** Test PDF Ingestion
4. **Incremental Sync:** Führe weiteren CRM-Sync aus (sollte nur Deltas fetchen)

---

**Letzte Aktualisierung:** 2026-01-09  
**Status:** ✅ Ready for Production

