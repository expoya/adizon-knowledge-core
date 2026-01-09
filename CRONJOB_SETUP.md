# 🕐 Cronjob Setup für CRM Sync

## Übersicht

Das System führt **Full Sync** durch (Incremental Sync deaktiviert wegen Zoho COQL Limitierungen).
Updates funktionieren automatisch über Neo4j MERGE mit `ON MATCH SET`.

## Performance-Zahlen

- **Datenmenge:** 58.741 Entities + 73.720 Relationships
- **Dauer:** ~6 Minuten (373 Sekunden)
- **Ressourcen:** Moderate CPU/RAM, keine Crashes

## Empfohlene Sync-Intervalle

### Option 1: Häufige Updates (Empfohlen)
```
Intervall: Alle 30 Minuten
Begründung: Schnelle Datenaktualität, ausreichend Pause zwischen Syncs
Cronjob: */30 * * * *
```

### Option 2: Business Hours
```
Intervall: Stündlich während Arbeitszeit (8-18 Uhr, Mo-Fr)
Begründung: Spart Ressourcen, CRM-Daten ändern sich hauptsächlich tagsüber
Cronjob: 0 8-18 * * 1-5
```

### Option 3: Konservativ
```
Intervall: Alle 2 Stunden
Begründung: Balance zwischen Aktualität und Ressourcen
Cronjob: 0 */2 * * *
```

## Railway Cronjob Einrichtung

### Methode 1: Railway Cron (Empfohlen)

**1. `railway.toml` erweitern:**

```toml
[[services]]
name = "backend"
# ... existing config ...

[[services.cron]]
schedule = "*/30 * * * *"  # Alle 30 Minuten
command = "curl -X POST https://your-app.up.railway.app/api/v1/crm-sync"
```

**2. Mit API Key absichern:**

```toml
[[services.cron]]
schedule = "*/30 * * * *"
command = "curl -X POST -H 'X-API-Key: ${CRON_API_KEY}' https://your-app.up.railway.app/api/v1/crm-sync"
```

### Methode 2: Externer Cron Service (Alternative)

**Services:**
- [EasyCron](https://www.easycron.com/)
- [Cron-job.org](https://cron-job.org/)
- [Railway Cron Jobs](https://docs.railway.app/reference/cron-jobs)

**Setup:**
1. Service registrieren
2. HTTP POST zu `/api/v1/crm-sync` konfigurieren
3. Intervall setzen (z.B. alle 30 Min)
4. Optional: API Key als Header hinzufügen

### Methode 3: Internal Scheduler (Python)

**Falls Railway Cron nicht verfügbar, im Backend:**

```python
# backend/app/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.crm_factory import get_crm_provider
from app.services.crm_sync.sync_orchestrator import CRMSyncOrchestrator

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('cron', minute='*/30')
async def sync_crm_data():
    """Sync CRM data every 30 minutes."""
    logger.info("🕐 Scheduled CRM sync starting...")
    try:
        provider = await get_crm_provider("zoho")
        orchestrator = CRMSyncOrchestrator(graph_store)
        result = await orchestrator.sync(provider)
        logger.info(f"✅ Scheduled sync completed: {result.message}")
    except Exception as e:
        logger.error(f"❌ Scheduled sync failed: {e}")

# In main.py:
@app.on_event("startup")
async def start_scheduler():
    scheduler.start()
    logger.info("✅ Scheduler started")
```

## API Endpoint Absicherung (Optional)

**Aktuell:** Endpoint ist öffentlich  
**Empfehlung:** API Key für Cronjob-Zugriff

```python
# backend/app/api/endpoints/ingestion.py
from fastapi import Header, HTTPException

@router.post("/crm-sync")
async def sync_crm(
    x_api_key: str = Header(None, alias="X-API-Key")
):
    # Optional: API Key check für Cronjobs
    if x_api_key and x_api_key != settings.cron_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    # ... existing sync logic ...
```

**Environment Variable:**
```bash
CRON_API_KEY=your-secret-key-here
```

## Monitoring

### Log Tracking
```bash
# Railway CLI
railway logs --filter "CRM Sync"

# Watch für Errors
railway logs --filter "ERROR" --follow
```

### Wichtige Metriken
- ✅ Sync Duration (soll ~6 Min bleiben)
- ✅ Entities synced (soll ~58k sein)
- ✅ Errors (sollen 0 sein)
- ✅ Memory usage (keine Crashes)

### Alerts Setup (Optional)

**Bei Railway:**
```toml
[[services.healthcheck]]
path = "/api/v1/health"
interval = 300  # 5 Minuten
timeout = 30
```

## Troubleshooting

### Sync dauert zu lange (>10 Min)
- **Ursache:** Zu viele Daten oder Neo4j Performance-Issues
- **Lösung:** Chunk Size reduzieren, Neo4j Memory erhöhen

### Memory Crashes
- **Ursache:** Zu große Batches
- **Lösung:** `chunk_size` in `node_batch_processor.py` von 1000 auf 500 reduzieren

### API Rate Limits
- **Ursache:** Zu häufige Syncs
- **Lösung:** Intervall von 30 Min auf 1 Stunde erhöhen

## Zukünftige Optimierungen

### Option A: REST API Incremental Sync
Die meisten Zoho Module unterstützen `modified_since` Parameter via REST API:

```python
# Für Deals, Tasks, Notes (REST API Module)
params = {
    "modified_since": "2026-01-09T20:00:00+00:00"
}
```

**Vorteile:**
- Nur geänderte Daten werden gefetcht
- Schneller (30 Sek statt 6 Min)
- Weniger API Calls

**Nachteile:**
- COQL Module (Leads, Accounts) bleiben Full Sync
- Komplexere Implementierung

### Option B: Hybrid Approach
- REST API Module: Incremental (modified_since)
- COQL Module: Full Sync (bleiben wie jetzt)
- Reduziert Sync-Zeit auf ~2-3 Minuten

## Best Practice Empfehlung

**Für Production:**

1. **Cronjob:** Alle 30 Minuten
2. **Monitoring:** Railway Logs + Health Check
3. **API Key:** Cronjob-Endpoint absichern
4. **Alerts:** Bei Failure Notification (Email/Slack)

**Implementierung:**

```bash
# 1. In railway.toml hinzufügen:
[[services.cron]]
schedule = "*/30 * * * *"
command = "curl -X POST -H 'X-API-Key: ${CRON_API_KEY}' https://adizon-knowledge-core.up.railway.app/api/v1/crm-sync"

# 2. Environment Variable setzen:
railway env set CRON_API_KEY=<generate-secure-key>

# 3. Deploy:
railway up

# 4. Monitor:
railway logs --follow
```

---

**Status:** ✅ Full Sync funktioniert stabil, Updates automatisch via MERGE  
**Nächster Schritt:** Cronjob in Railway einrichten

