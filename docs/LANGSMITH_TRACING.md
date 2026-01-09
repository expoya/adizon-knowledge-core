# LangSmith Tracing Setup

## Übersicht

LangSmith ist das offizielle Tracing & Debugging Tool von LangChain. Es ermöglicht:
- ✅ Visualisierung der gesamten Agent-Chain
- ✅ Debugging von LLM-Calls und Tool-Aufrufen
- ✅ Performance-Monitoring
- ✅ Prompt-Testing und -Optimierung

---

## Setup (in 3 Minuten)

### 1. LangSmith Account erstellen

Gehe zu: [smith.langchain.com](https://smith.langchain.com)

- Registriere dich (kostenlos für Development)
- Erstelle ein neues Projekt (z.B. "adizon-knowledge-core")

### 2. API Key erhalten

In LangSmith Dashboard:
1. Gehe zu **Settings** → **API Keys**
2. Klicke **Create API Key**
3. Kopiere den Key (z.B. `sk_lsv2_pt_...`)

### 3. Environment Variables setzen

Füge diese 3 Variablen zu deiner `.env` Datei hinzu:

```bash
# LangSmith Tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=adizon-knowledge-core
LANGCHAIN_API_KEY=sk_lsv2_pt_YOUR_KEY_HERE
```

**Docker/Railway:**  
Füge die gleichen Variablen in die Railway Environment Variables ein.

### 4. Backend neu starten

```bash
# Lokal
cd backend
uvicorn app.main:app --reload

# Docker
docker-compose restart backend
```

---

## ✅ Verification

Nach dem Setup solltest du in den Logs sehen:

```
INFO:     Started server process [1]
INFO:     Application startup complete.
```

**In LangSmith:**  
Gehe zu [smith.langchain.com/projects](https://smith.langchain.com/projects)  
→ Öffne dein Projekt  
→ Nach der ersten Query siehst du Traces!

---

## 📊 Was du sehen wirst

### Chain Visualization

```
User Query
  ↓
Router Node (LLM Classification)
  ├─ SQL Intent?
  │   ↓
  │   SQL Node
  │   ├─ get_sql_schema Tool
  │   └─ execute_sql_query Tool
  │
  └─ Knowledge Intent?
      ↓
      Knowledge Node
      └─ search_knowledge_base Tool
          ├─ Vector Search (PGVector)
          └─ Graph Search (Neo4j)
```

### Debugging Information

Jeder Schritt zeigt:
- **Inputs:** Was kam rein?
- **Outputs:** Was kam raus?
- **Latency:** Wie lange dauerte es?
- **Tokens:** Wie viele Tokens wurden verwendet?
- **Errors:** Falls etwas schief ging

---

## 🔍 Debugging Example

**Scenario:** Agent wählt SQL Tool statt Knowledge Tool

**In LangSmith:**
1. Öffne die Trace der Query
2. Klicke auf "Router Node"
3. Sieh dir den Prompt an:
   ```
   INTENT TYPES:
   - "sql": Frage nach finanziellen Daten...
   - "knowledge": Frage nach CRM-Daten...
   ```
4. Sieh die LLM Response:
   ```
   sql  ← FALSCH!
   ```
5. **Erkenntniss:** Der Prompt muss klarer sein

**Fix:** Prompt anpassen in `chat_workflow.py` und neu testen.

---

## 🎯 Use Cases

### 1. Router Debugging

**Problem:** Agent wählt falsches Tool

**LangSmith zeigt:**
- Welchen Prompt der Router bekam
- Wie der LLM klassifizierte
- Warum er sich für Tool X entschied

**Fix:** Prompt in `chat_workflow.py` verbessern

---

### 2. Tool Failure Debugging

**Problem:** Tool gibt Error zurück

**LangSmith zeigt:**
- Welche Parameter wurden übergeben
- Was war die genaue Fehlermeldung
- Welche Tools danach aufgerufen wurden

**Fix:** Tool-Validierung verbessern

---

### 3. Performance Optimization

**Problem:** Agent ist langsam

**LangSmith zeigt:**
- Welcher Schritt dauert am längsten
- Wie viele LLM Calls gemacht werden
- Ob unnötige Tool-Calls existieren

**Fix:** Caching, parallele Calls, oder Prompt-Optimierung

---

## 🛠️ Console Logging vs LangSmith

**Console Logging (aktuell aktiv):**
```
[ROUTER] User Query: Welche Kunden hatten einen Einwand?
[ROUTER] LLM Classification: 'knowledge' → Intent: 'knowledge'
[ROUTER] ✅ Final Intent: 'knowledge'
[ROUTER] Next Node: knowledge_node
[KNOWLEDGE_NODE] 📚 Executing Knowledge Node
[KNOWLEDGE_NODE] Tool: search_knowledge_base (Vector + Graph)
```

**LangSmith (zusätzlich):**
- Visueller Graph der Chain
- Token Usage pro Schritt
- Latency Waterfall
- Complete Prompt & Response für jeden LLM Call
- Error Stacktraces

---

## 💡 Best Practices

### 1. Separate Projekte für Environments

```bash
# Development
LANGCHAIN_PROJECT=adizon-dev

# Staging
LANGCHAIN_PROJECT=adizon-staging

# Production
LANGCHAIN_PROJECT=adizon-prod
```

### 2. Tagging wichtiger Queries

```python
# In Code (optional)
from langsmith import trace

@trace(tags=["important-customer", "debug"])
async def special_query(query: str):
    ...
```

### 3. Filter & Search

In LangSmith UI:
- Filter by: Status (success/error)
- Filter by: Latency (> 5s)
- Filter by: Tag
- Search: Specific query text

---

## 🚫 Troubleshooting

### "No traces appearing"

**Check:**
1. `LANGCHAIN_TRACING_V2=true` (nicht "True" oder "1")
2. API Key ist korrekt (beginnt mit `sk_lsv2_pt_`)
3. Backend wurde neu gestartet
4. Firewall erlaubt Outbound zu `api.smith.langchain.com`

**Test:**
```bash
# In backend container/shell
python -c "import os; print(os.getenv('LANGCHAIN_TRACING_V2'))"
# Should print: true
```

### "Authentication Error"

**Check:**
- API Key in LangSmith regenerieren
- Neue Key in `.env` setzen
- Backend neu starten

### "Rate Limit Exceeded"

**Free Tier Limits:**
- 5,000 traces/month
- 50 MB storage

**Lösung:**
- Upgrade zu bezahltem Plan
- ODER: Tracing nur bei Bedarf aktivieren (ENV var ändern)

---

## 📚 Weitere Resources

- **LangSmith Docs:** [docs.smith.langchain.com](https://docs.smith.langchain.com)
- **Tutorial Video:** [LangSmith Tracing Basics](https://www.youtube.com/watch?v=...)
- **LangChain Discord:** Support Community

---

## 🎓 Quick Start Checklist

- [ ] Account bei smith.langchain.com erstellt
- [ ] API Key kopiert
- [ ] 3 ENV Vars in `.env` gesetzt
- [ ] Backend neu gestartet
- [ ] Test-Query im Chat gemacht
- [ ] Trace in LangSmith Dashboard sichtbar

**Wenn alle Checkboxen ✅ sind: Du bist bereit!** 🚀

---

**Status:** Ready for Production  
**Updated:** 2026-01-10

