# Performance & Load Testing

Lasttest-Suite für Adizon Knowledge Core mit [Locust](https://locust.io/).

## Installation

```bash
pip install locust
```

## Quick Start

1. **Backend starten** (in einem separaten Terminal):
   ```bash
   cd backend
   uvicorn main:app --reload --port 8000
   ```

2. **Locust starten**:
   ```bash
   locust -f tests/performance/locustfile.py --host http://localhost:8000
   ```

3. **Web-Interface öffnen**: [http://localhost:8089](http://localhost:8089)

4. **Test konfigurieren**:
   - **Number of users**: Anzahl der simulierten Benutzer (z.B. 10, 50, 100)
   - **Spawn rate**: Wie schnell Benutzer hinzugefügt werden (z.B. 5/Sekunde)
   - **Host**: API-URL (bereits vorausgefüllt)

5. **Start swarming** klicken

## Benutzer-Profile

Die Suite definiert drei Benutzertypen mit unterschiedlichen Verhaltensmustern:

### TheChatter (Gewichtung: 10)
Simuliert Chat-Interaktionen mit dem LLM.

- **Endpunkt**: `POST /api/v1/chat`
- **Verhalten**: Sendet kurze und lange Nachrichten
- **Wartezeit**: 1-5 Sekunden zwischen Anfragen
- **Testziel**: LLM-Orchestrierung, Response-Zeiten

### TheResearcher (Gewichtung: 5)
Führt komplexe Such- und Graph-Abfragen durch.

- **Endpunkte**:
  - `POST /api/v1/graph/query` - Cypher-Abfragen
  - `GET /api/v1/knowledge/search` - Semantische Suche
  - `GET /api/v1/knowledge/summary` - Wissensbasis-Übersicht
  - `GET /api/v1/documents` - Dokumentenliste
- **Wartezeit**: 2-8 Sekunden
- **Testziel**: Neo4j Connection Pooling, pgvector Performance

### TheUploader (Gewichtung: 1)
Lädt Dokumente hoch, um File-Handling zu testen.

- **Endpunkt**: `POST /api/v1/upload`
- **Verhalten**: Generiert dynamisch PDF-Dateien (10-50KB)
- **Wartezeit**: 5-15 Sekunden
- **Testziel**: RAM-Verbrauch, File-Processing unter Last

## Typische Testszenarien

### Smoke Test (Schnelltest)
```bash
locust -f tests/performance/locustfile.py --host http://localhost:8000 \
  --users 5 --spawn-rate 1 --run-time 1m --headless
```

### Load Test (Normallast)
```bash
locust -f tests/performance/locustfile.py --host http://localhost:8000 \
  --users 50 --spawn-rate 5 --run-time 10m --headless
```

### Stress Test (Überlast)
```bash
locust -f tests/performance/locustfile.py --host http://localhost:8000 \
  --users 200 --spawn-rate 20 --run-time 15m --headless
```

### Endurance Test (Langzeittest)
```bash
locust -f tests/performance/locustfile.py --host http://localhost:8000 \
  --users 30 --spawn-rate 2 --run-time 1h --headless
```

## Kommandozeilen-Optionen

| Option | Beschreibung |
|--------|--------------|
| `--host` | Ziel-URL der API |
| `--users` | Anzahl gleichzeitiger Benutzer |
| `--spawn-rate` | Benutzer pro Sekunde hinzufügen |
| `--run-time` | Testdauer (z.B. `5m`, `1h`) |
| `--headless` | Ohne Web-Interface (für CI/CD) |
| `--html report.html` | HTML-Report generieren |
| `--csv results` | CSV-Metriken exportieren |

## Metriken interpretieren

### Im Web-Interface (Port 8089)

- **Statistics**: Request-Statistiken (RPS, Response Times, Failures)
- **Charts**: Echtzeit-Graphen für Throughput und Latenz
- **Failures**: Liste aller fehlgeschlagenen Requests
- **Download Data**: CSV-Export für weitere Analyse

### Wichtige Kennzahlen

| Metrik | Beschreibung | Zielwert |
|--------|--------------|----------|
| **Median Response Time** | 50. Perzentil | < 500ms (API), < 5s (Chat) |
| **95th Percentile** | Langsame Requests | < 2s (API), < 15s (Chat) |
| **Requests/s** | Durchsatz | Je nach Infrastruktur |
| **Failure Rate** | Fehlerquote | < 1% |

## Fehler-Behandlung

Die Suite behandelt folgende Fehlerzustände:

| HTTP Code | Bedeutung | Aktion |
|-----------|-----------|--------|
| 200 | Erfolg | Als Erfolg gewertet |
| 409 | Duplikat (Upload) | Als Erfolg gewertet |
| 503 | Service Unavailable | Als Fehler geloggt, Test läuft weiter |
| 403 | Security Block | Als Fehler geloggt, Test läuft weiter |
| 422 | Validation Error | Als Fehler geloggt, Test läuft weiter |

## CI/CD Integration

Beispiel für GitHub Actions:

```yaml
- name: Run Load Tests
  run: |
    pip install locust
    locust -f tests/performance/locustfile.py \
      --host ${{ secrets.API_URL }} \
      --users 20 \
      --spawn-rate 5 \
      --run-time 5m \
      --headless \
      --html loadtest-report.html \
      --exit-code-on-error 1
```

## Troubleshooting

### "Connection refused"
- Backend läuft nicht oder falsche Host-URL
- Prüfe: `curl http://localhost:8000/api/v1/health`

### Sehr hohe Fehlerrate
- Backend überlastet (CPU, Memory, DB-Connections)
- Reduziere `--users` oder erhöhe `--spawn-rate` Intervall

### Locust startet nicht
- Prüfe Python-Version (3.8+)
- Prüfe Installation: `locust --version`
