# Changelog: Hybrid Architecture & Multi-Tenant Ontology

**Datum:** 2025-01-04
**Version:** 2.0.0
**Autor:** Claude Code

## Zusammenfassung

Umstellung auf mandantenfähige Architektur mit dynamischer Ontology-Konfiguration und ausgelagertem Compute-Worker.

---

## Neue Features

### 1. Dynamisches Ontology-System

**Ziel:** Keine hardcodierten, firmenspezifischen Klassen mehr.

**Neue Dateien:**
- `backend/app/config/ontology_voltage.yaml` - YAML-basierte Domain-Definition
- `backend/app/services/schema_factory.py` - Dynamische Pydantic Model-Generierung

**Funktionsweise:**
```yaml
# ontology_voltage.yaml
domain_name: "Voltage Solutions"
node_types:
  - name: "ORGANIZATION"
    description: "Companies, Suppliers, Clients"
relationship_types:
  - name: "WORKS_FOR"
    description: "Employment relationship"
```

SchemaFactory erzeugt zur Laufzeit:
- `DynamicNode` mit Literal-Type für erlaubte Node-Types
- `DynamicRelationship` mit Literal-Type für Relationship-Types
- `ExtractionResult` Container-Model
- System-Prompt für LLM mit allen Beschreibungen

**Konfiguration:**
```
ONTOLOGY_PATH=app/config/ontology_voltage.yaml
```

### 2. Trooper Worker Microservice

**Ziel:** Compute-intensive Operationen auslagern.

**Neue Struktur:**
```
trooper_worker/
├── main.py              # FastAPI mit BackgroundTasks
├── workflow.py          # LangGraph Ingestion Pipeline
├── core/config.py       # Worker-Konfiguration
├── services/
│   ├── storage.py       # MinIO Download
│   ├── vector_store.py  # PGVector
│   ├── graph_store.py   # Neo4j
│   └── schema_factory.py
├── config/
│   └── ontology_voltage.yaml
├── requirements.txt
└── Dockerfile.trooper
```

**System-Dependencies (für OCR):**
- libmagic-dev
- poppler-utils
- tesseract-ocr
- tesseract-ocr-deu

### 3. Backend als Dispatcher

**Vorher:** Backend führte komplette Ingestion aus (LangChain, LLM, etc.)

**Nachher:** Backend sendet nur HTTP-Request an Trooper:

```python
# backend/app/graph/ingestion_workflow.py
async def run_ingestion_workflow(...):
    response = await client.post(
        f"{settings.trooper_url}/ingest",
        json={"document_id": ..., "filename": ..., "storage_path": ...},
        headers={"Authorization": f"Bearer {settings.trooper_auth_token}"}
    )
```

### 4. Status-Callback Endpoint

**Neuer Endpoint:** `POST /api/v1/documents/{id}/status`

Wird vom Trooper Worker aufgerufen nach Verarbeitung:
```json
{
  "status": "INDEXED",  // oder "ERROR"
  "error_message": null
}
```

---

## Geänderte Dateien

### backend/app/core/config.py

**Neue Settings:**
```python
ontology_path: str = Field(
    default="app/config/ontology_voltage.yaml",
    alias="ONTOLOGY_PATH",
)
trooper_url: str = Field(
    default="http://localhost:8001",
    alias="TROOPER_URL",
)
trooper_auth_token: str | None = Field(
    default=None,
    alias="TROOPER_AUTH_TOKEN",
)
```

### backend/app/graph/ingestion_workflow.py

**Komplett ersetzt:** Von 500 Zeilen LangGraph-Workflow zu 85 Zeilen HTTP-Dispatcher.

- Entfernt: LangChain, LLMGraphTransformer, alle Nodes
- Hinzugefügt: `httpx.AsyncClient`, Auth-Header Support
- Neue Exception: `TrooperDispatchError`

### backend/app/api/endpoints/ingestion.py

**Neue Models:**
- `StatusUpdateRequest` (status, error_message)
- `StatusUpdateResponse` (document_id, status, message)

**Neuer Endpoint:**
- `POST /documents/{document_id}/status`

---

## Deployment

### docker-compose.yml (deployment/trooper/)

```yaml
services:
  adizon-worker:
    build:
      context: ../../trooper_worker
      dockerfile: Dockerfile.trooper
    networks:
      - my-ai-stack_default
    environment:
      - POSTGRES_HOST, NEO4J_URI, MINIO_ENDPOINT, ...
      - BACKEND_URL=http://adizon-backend:8000
```

### Caddy Integration

```caddy
handle_path /worker/* {
    reverse_proxy @auth adizon-worker:8000
}
```

---

## Migration

### Für bestehende Installationen:

1. **Backend .env ergänzen:**
   ```
   TROOPER_URL=http://adizon-worker:8000
   TROOPER_AUTH_TOKEN=<optional>
   ONTOLOGY_PATH=app/config/ontology_voltage.yaml
   ```

2. **Trooper Worker deployen:**
   ```bash
   cd deployment/trooper
   cp .env.example .env
   # .env anpassen
   docker-compose up -d --build
   ```

3. **Caddy konfigurieren** (falls hinter Reverse Proxy)

### Für neue Mandanten:

1. Neue `ontology_<mandant>.yaml` erstellen
2. `ONTOLOGY_PATH` in Worker-Umgebung setzen
3. Worker neu starten

---

## Breaking Changes

- `backend/app/graph/ingestion_workflow.py` enthält keine Workflow-Logik mehr
- Import `from langchain_experimental.graph_transformers import LLMGraphTransformer` entfernt
- Trooper Worker **muss** laufen für Document Processing
- Ohne Worker: Uploads werden akzeptiert, aber nie verarbeitet (PENDING forever)

---

## Architektur-Entscheidungen

1. **Fire-and-Forget Pattern:** Backend wartet nicht auf Verarbeitung. Worker ruft zurück.

2. **Shared Database Access:** Worker greift direkt auf PostgreSQL/Neo4j zu (kein API-Gateway).

3. **Ontology als Code:** YAML statt Python-Klassen für einfache Mandanten-Konfiguration.

4. **OCR-Ready:** Worker-Dockerfile enthält Tesseract für gescannte PDFs.
