# Deployment Guide

## Lokale Entwicklung

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ (für Frontend-Entwicklung)
- Python 3.11+ (für Backend-Entwicklung)

### Quick Start

```bash
# Repository klonen
git clone https://github.com/expoya/adizon-knowledge-core.git
cd adizon-knowledge-core

# Environment vorbereiten
cp backend/.env.example backend/.env
# .env anpassen (EMBEDDING_API_URL, EMBEDDING_API_KEY erforderlich!)

# Stack starten
docker-compose up -d

# Logs verfolgen
docker-compose logs -f backend
```

### Services

| Service | Port | URL |
|---------|------|-----|
| Frontend | 80 | http://localhost |
| Backend | 8000 | http://localhost:8000 |
| PostgreSQL | 5432 | localhost:5432 |
| Neo4j Browser | 7474 | http://localhost:7474 |
| Neo4j Bolt | 7687 | bolt://localhost:7687 |
| MinIO Console | 9001 | http://localhost:9001 |
| MinIO API | 9000 | localhost:9000 |

---

## Trooper Worker Deployment

Der Worker läuft separat auf GPU-fähiger Infrastruktur.

### 1. Verzeichnis vorbereiten

```bash
cd deployment/trooper
cp .env.example .env
```

### 2. Environment konfigurieren

```bash
# .env bearbeiten
POSTGRES_HOST=<postgres-host>
POSTGRES_PASSWORD=<password>
NEO4J_URI=bolt://<neo4j-host>:7687
NEO4J_PASSWORD=<password>
MINIO_ENDPOINT=<minio-host>:9000
MINIO_ACCESS_KEY=<key>
MINIO_SECRET_KEY=<secret>
EMBEDDING_API_URL=<trooper-llm-url>
EMBEDDING_API_KEY=<api-key>
BACKEND_URL=http://<backend-host>:8000
```

### 3. Worker starten

```bash
docker-compose up -d --build
```

### 4. Health Check

```bash
curl http://localhost:8000/health
# {"status": "healthy", "service": "trooper-worker"}
```

---

## Backend für Worker konfigurieren

In `backend/.env`:

```bash
# Trooper Worker URL (intern oder via Reverse Proxy)
TROOPER_URL=http://adizon-worker:8000

# Optional: Auth Token für Caddy/Reverse Proxy
TROOPER_AUTH_TOKEN=<bearer-token>
```

---

## Caddy Reverse Proxy

Falls Worker hinter Caddy läuft:

```caddy
# In Caddyfile hinzufügen
handle_path /worker/* {
    @auth {
        header Authorization Bearer*
    }
    reverse_proxy @auth adizon-worker:8000
}
```

Backend-Konfiguration:
```bash
TROOPER_URL=https://domain.com/worker
TROOPER_AUTH_TOKEN=<caddy-auth-token>
```

---

## Railway Deployment

### Backend

1. Railway Projekt erstellen
2. PostgreSQL Plugin hinzufügen
3. GitHub Repository verbinden
4. Environment Variables setzen:

```
DATABASE_URL=<von Railway>
NEO4J_URI=<externe Neo4j Instanz>
NEO4J_USER=neo4j
NEO4J_PASSWORD=<password>
MINIO_ENDPOINT=<externe MinIO>
MINIO_ACCESS_KEY=<key>
MINIO_SECRET_KEY=<secret>
EMBEDDING_API_URL=<api-url>
EMBEDDING_API_KEY=<key>
TROOPER_URL=<worker-url>
```

5. Deploy triggern

### Frontend

Separates Railway Service mit:
```
VITE_API_URL=https://<backend>.railway.app/api/v1
```

---

## Docker Images

### Backend

```dockerfile
FROM python:3.11-slim
# Standard Python deps
```

### Trooper Worker

```dockerfile
FROM python:3.11-slim
# + System deps für OCR:
# libmagic-dev, poppler-utils, tesseract-ocr, tesseract-ocr-deu
```

### Frontend

```dockerfile
# Multi-stage build
FROM node:18-alpine AS build
# Build React app

FROM nginx:alpine
# Serve static files
```

---

## Netzwerk-Architektur

### Docker Network (lokal)

```
┌─────────────────────────────────────────────────────────┐
│                    docker network                        │
│  ┌──────────┐ ┌──────────┐ ┌───────┐ ┌───────┐         │
│  │ postgres │ │  neo4j   │ │ minio │ │backend│         │
│  │  :5432   │ │:7474/7687│ │:9000  │ │ :8000 │         │
│  └──────────┘ └──────────┘ └───────┘ └───────┘         │
│                                                         │
│                      ┌──────────┐                       │
│                      │ frontend │                       │
│                      │   :80    │                       │
│                      └──────────┘                       │
└─────────────────────────────────────────────────────────┘
```

### Produktions-Setup

```
┌─────────────────┐
│    Internet     │
└────────┬────────┘
         │
    ┌────▼────┐
    │  Caddy  │ (TLS, Auth, Routing)
    └────┬────┘
         │
    ┌────┴────────────┬──────────────┐
    │                 │              │
┌───▼───┐        ┌────▼───┐    ┌─────▼─────┐
│Backend│        │Frontend│    │  Worker   │
│ :8000 │        │  :80   │    │   :8000   │
└───┬───┘        └────────┘    └─────┬─────┘
    │                                │
    └────────────┬───────────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
┌───▼───┐   ┌────▼───┐   ┌────▼───┐
│Postgres│   │ Neo4j  │   │ MinIO  │
└────────┘   └────────┘   └────────┘
```

---

## Troubleshooting

### Worker nicht erreichbar

```bash
# Backend Logs prüfen
docker logs adizon-backend 2>&1 | grep -i trooper

# Worker Health Check
curl http://<worker-host>:8000/health
```

### Dokumente bleiben PENDING

1. Worker läuft nicht
2. Worker kann Backend nicht erreichen (BACKEND_URL falsch)
3. Datenbank-Verbindung im Worker fehlgeschlagen

```bash
# Worker Logs
docker logs adizon-worker -f
```

### Neo4j Verbindungsfehler

```bash
# Neo4j erreichbar?
curl http://<neo4j-host>:7474

# Credentials korrekt?
cypher-shell -a bolt://<host>:7687 -u neo4j -p <password>
```

### MinIO Fehler

```bash
# Bucket existiert?
mc ls myminio/knowledge-documents

# Bucket erstellen
mc mb myminio/knowledge-documents
```
