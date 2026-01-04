# Adizon Knowledge Core - Dokumentation

## Inhaltsverzeichnis

| Dokument | Beschreibung |
|----------|--------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Systemarchitektur, Tech Stack, Datenfluss |
| [API.md](API.md) | REST API Reference |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Deployment Guide (Local, Docker, Railway) |
| [ONTOLOGY.md](ONTOLOGY.md) | Ontology-Konfiguration für Multi-Tenant |
| [changelogs/](changelogs/) | Änderungsprotokolle |

## Quick Links

### Für Entwickler

- [Lokale Entwicklung starten](DEPLOYMENT.md#lokale-entwicklung)
- [API Endpoints](API.md)
- [Architektur-Übersicht](ARCHITECTURE.md#overview)

### Für Administratoren

- [Trooper Worker deployen](DEPLOYMENT.md#trooper-worker-deployment)
- [Neue Ontologie erstellen](ONTOLOGY.md#neue-ontologie-erstellen)
- [Troubleshooting](DEPLOYMENT.md#troubleshooting)

### Changelogs

- [2025-01-04: Hybrid Architecture](changelogs/2025-01-04_hybrid-architecture.md) - Multi-Tenant Ontology, Trooper Worker

## Projekt-Übersicht

```
adizon-knowledge-core/
├── backend/           # FastAPI Backend
├── frontend/          # React Frontend
├── trooper_worker/    # Compute Worker
├── deployment/        # Deployment Configs
├── docs/              # Dokumentation (hier)
└── docker-compose.yml # Local Stack
```

## Support

- GitHub Issues: https://github.com/expoya/adizon-knowledge-core/issues
