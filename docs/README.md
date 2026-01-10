# Adizon Knowledge Core - Dokumentation

Willkommen zur Dokumentation des Adizon Knowledge Core Systems!

## 📚 Hauptdokumentation

### Architektur & Konzepte
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System-Architektur und Datenflüsse
- **[AGENTIC_RAG.md](AGENTIC_RAG.md)** - Agentic RAG v2.0 Features & Workflow
- **[GRAPH_SCHEMA.md](GRAPH_SCHEMA.md)** - Neo4j Graph Schema (12+ Node Types, 14 Relationships)
- **[ONTOLOGY.md](ONTOLOGY.md)** - Ontologie und Entity-Definitionen

### API & Integration
- **[API.md](API.md)** - Vollständige API-Referenz
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Deployment-Anleitung (Railway, Docker)
- **[LANGSMITH_TRACING.md](LANGSMITH_TRACING.md)** - LangSmith Tracing Setup
- **[QUICK_START.md](QUICK_START.md)** - Schnellstart-Anleitung

---

## 📋 Changelogs

Chronologische Übersicht aller wichtigen Updates:

- **[2026-01-10: Graph Schema V2](changelogs/2026-01-10_graph-schema-v2.md)** - Typisiertes Neo4j Schema mit Multi-Label Nodes
- **[2026-01-09: Phase 1 Success](changelogs/2026-01-09_phase1-success.md)** - Vollständiger CRM-Import erfolgreich (5.100+ Entities)
- **[2026-01-09: Phase 1 Complete](changelogs/2026-01-09_phase1-complete.md)** - Technische Details zum Full Import
- **[2026-01-08: CRM Integration](changelogs/2026-01-08_crm-integration.md)** - Zoho CRM Plugin-System v2.1
- **[2026-01-08: Agentic RAG v2](changelogs/2026-01-08_agentic-rag-v2.md)** - LangGraph-basiertes Routing
- **[2025-01-04: Hybrid Architecture](changelogs/2025-01-04_hybrid-architecture.md)** - Vector + Graph Hybrid-Ansatz

---

## 🛠️ Implementation Guides

Schritt-für-Schritt Anleitungen für spezifische Features:

### Zoho CRM Integration
- **[OAUTH_SCOPE_GUIDE.md](implementation-guides/OAUTH_SCOPE_GUIDE.md)** - OAuth2 Setup für Zoho (Scopes, Token-Generierung)
- **[ZOHO_BOOKS_SETUP.md](implementation-guides/ZOHO_BOOKS_SETUP.md)** - Zoho Books API Integration
- **[ZOHO_FINANCE_EMAILS_RESEARCH.md](implementation-guides/ZOHO_FINANCE_EMAILS_RESEARCH.md)** - Invoices, Subscriptions & Emails
- **[REST_API_MODULES.md](implementation-guides/REST_API_MODULES.md)** - REST API Support für Finance-Module
- **[CRONJOB_SETUP.md](implementation-guides/CRONJOB_SETUP.md)** - Automatische CRM-Synchronisation (Cron Jobs)

---

## 🐛 Troubleshooting

Bekannte Probleme und deren Lösungen:

- **[ORPHAN_NODES_FIX.md](troubleshooting/ORPHAN_NODES_FIX.md)** - Fix für CRMEntity Orphan Nodes (MERGE → MATCH)
- **[ZOHO_COQL_LIMITATION.md](troubleshooting/ZOHO_COQL_LIMITATION.md)** - COQL Lookup-Felder Limitation (owner_name NULL)
- **[SMOKE_TEST_FIXES.md](troubleshooting/SMOKE_TEST_FIXES.md)** - Datenqualitäts-Fixes (Lead Names, created_time)
- **[CHECK_EMAILS_MODULE.md](troubleshooting/CHECK_EMAILS_MODULE.md)** - Email-Modul Recherche (Related Lists)

---

## 📦 Archiv

Nicht mehr aktuelle Dokumentation (historisch):

- **[SMOKE_TEST.md](archive/SMOKE_TEST.md)** - Smoke Test Dokumentation (LIMIT 50)
- **[README_SMOKE_TEST.md](archive/README_SMOKE_TEST.md)** - Smoke Test Quick Start
- **[TEST_CHECKLIST.md](archive/TEST_CHECKLIST.md)** - Test-Checkliste Smoke → Full Import

---

## 🚀 Quick Links

### Für Entwickler
1. Start: [QUICK_START.md](QUICK_START.md)
2. API: [API.md](API.md)
3. Architektur: [ARCHITECTURE.md](ARCHITECTURE.md)

### Für Admins
1. Deployment: [DEPLOYMENT.md](DEPLOYMENT.md)
2. CRM Setup: [implementation-guides/OAUTH_SCOPE_GUIDE.md](implementation-guides/OAUTH_SCOPE_GUIDE.md)
3. Monitoring: [LANGSMITH_TRACING.md](LANGSMITH_TRACING.md)

### Bei Problemen
1. Troubleshooting: [troubleshooting/](troubleshooting/)
2. Changelogs: [changelogs/](changelogs/)
3. GitHub Issues

---

## 📊 Aktueller Status

**Version:** 2.1 (Agentic RAG + CRM Integration)

**Features:**
- ✅ Agentic RAG mit LangGraph
- ✅ Zoho CRM Integration (11+ Module)
- ✅ Graph Schema V2 (Multi-Label Nodes)
- ✅ Full CRM Import (5.100+ Entities)
- ✅ Incremental Sync (Modified_Time Filter)
- ✅ Zoho Books Integration (600+ Invoices)
- ⏳ Email Fetching (Related Lists)

**Nächste Schritte:**
- Phase 2: Incremental Sync Optimierung
- Phase 3: Custom Fields Discovery
- Phase 4: Monitoring & Alerting

---

**Letzte Aktualisierung:** 2026-01-10  
**Maintainer:** Adizon GmbH
