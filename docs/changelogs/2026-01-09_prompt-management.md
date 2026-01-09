# Changelog: Prompt Management System

**Datum:** 2026-01-09  
**Typ:** Feature / Refactoring  
**Bereich:** Backend - LangGraph Workflow

## 🎯 Ziel

Trennung von Prompts und Code für bessere Wartbarkeit, Sicherheit und einfacheres Prompt-Engineering.

## ✨ Änderungen

### 1. Neue Prompt-Management-Struktur

Erstellt: `backend/prompts/` Ordner mit:

```
prompts/
├── __init__.py                    # PromptLoader Utility mit Caching
├── README.md                      # Dokumentation
├── intent_classification.txt     # Router: Intent Detection
├── sql_generation.txt            # SQL Node: Query Generation
└── answer_generation.txt         # Generator: Final Answer
```

### 2. PromptLoader Utility

**Features:**
- **Lazy Loading**: Prompts werden bei Bedarf geladen
- **Caching**: Einmal geladene Prompts werden gecacht
- **Reload**: Hot-Reload für Prompt-Änderungen ohne Server-Restart
- **Error Handling**: Klare Fehlermeldungen bei fehlenden Prompts
- **List Available**: Übersicht aller verfügbaren Prompts

**API:**
```python
from prompts import get_prompt, PromptLoader

# Lade einen Prompt
prompt = get_prompt("intent_classification")

# Verwende mit Platzhaltern
formatted = prompt.format(query="Was sind unsere Top-Kunden?")

# Verfügbare Prompts auflisten
available = PromptLoader.list_available()

# Prompt neu laden (z.B. nach Änderung)
PromptLoader.reload("intent_classification")
```

### 3. Refactoring von chat_workflow.py

**Vorher:**
- 3 große inline Prompts (87 Zeilen Prompt-Code)
- Schwierig zu bearbeiten und zu testen
- Prompts vermischt mit Business Logic

**Nachher:**
- Import: `from prompts import get_prompt`
- Laden: `prompt = get_prompt("intent_classification")`
- 3 Zeilen Code statt 87 Zeilen Prompt-String

**Geänderte Nodes:**
1. **router_node**: `classification_prompt` → `intent_classification.txt`
2. **sql_node**: `sql_generation_prompt` → `sql_generation.txt`
3. **generation_node**: `generation_prompt` → `answer_generation.txt`

## ✅ Vorteile

### Sicherheit
- ✅ Prompts können nicht versehentlich Code überschreiben
- ✅ Keine String-Escaping-Probleme in Python-Code
- ✅ Klare Trennung von Logik und Inhalt

### Wartbarkeit
- ✅ Prompts einfach bearbeitbar (nur Text)
- ✅ Git zeigt Prompt-Änderungen sauber an
- ✅ Keine Indentation-Probleme
- ✅ Kein String-Formatting-Overhead im Code

### Entwicklung
- ✅ Prompt-Engineering ohne Code-Änderungen
- ✅ Einfache A/B-Tests von Prompts
- ✅ Versionierung von Prompts möglich
- ✅ Hot-Reload für schnelles Iterieren

### Performance
- ✅ Prompts werden beim Start pre-loaded
- ✅ Caching verhindert wiederholtes File-Lesen
- ✅ Keine Performance-Regression

## 📝 Verwendung

### Neuen Prompt hinzufügen

1. Erstelle `backend/prompts/my_new_prompt.txt`:
```txt
Du bist ein hilfreicher Assistent.

EINGABE:
{input}

AUSGABE:
```

2. Verwende im Code:
```python
from prompts import get_prompt

prompt = get_prompt("my_new_prompt")
formatted = prompt.format(input="Hallo")
```

### Prompt bearbeiten

1. Öffne die entsprechende `.txt` Datei
2. Bearbeite den Text
3. Speichere
4. Optional: `PromptLoader.reload("prompt_name")`

### Prompt-Platzhalter

Alle Prompts unterstützen Python `.format()` Syntax:
- `{query}` - Benutzer-Query
- `{context}` - Kontext-Informationen
- `{schema}` - Datenbank-Schema
- etc.

## 🔄 Migration

| Vorher (inline) | Nachher (file-based) |
|----------------|----------------------|
| 87 Zeilen Prompt-Strings in `chat_workflow.py` | 3x `get_prompt(...)` |
| Schwierig zu bearbeiten | Einfach zu bearbeiten |
| Code-Reviews kompliziert | Text-Dateien übersichtlich |
| String-Escaping nötig | Keine Escaping-Probleme |

## 🧪 Tests

**Manuelle Tests:**
- ✅ Intent Classification funktioniert
- ✅ SQL Generation funktioniert
- ✅ Answer Generation funktioniert
- ✅ PromptLoader lädt alle 3 Prompts beim Import
- ✅ Fehlerbehandlung bei fehlendem Prompt

**Zukünftige Tests:**
- Unit Tests für PromptLoader
- Integration Tests für Prompt-Loading
- A/B-Tests für verschiedene Prompt-Versionen

## 📊 Impact

### Code-Reduktion
- `chat_workflow.py`: -84 Zeilen (Prompts entfernt)
- Neue Files: +203 Zeilen (Prompts + Utility + Docs)
- **Net:** +119 Zeilen, aber viel bessere Organisation

### Dateien geändert
- **Modified:** `backend/app/graph/chat_workflow.py` (Prompts extrahiert)
- **New:** `backend/prompts/__init__.py` (PromptLoader)
- **New:** `backend/prompts/intent_classification.txt`
- **New:** `backend/prompts/sql_generation.txt`
- **New:** `backend/prompts/answer_generation.txt`
- **New:** `backend/prompts/README.md`

## 🚀 Next Steps

1. ✅ **Deployment auf Railway** - Testen ob Prompts korrekt geladen werden
2. ⏳ Unit Tests für PromptLoader schreiben
3. ⏳ Weitere Prompts extrahieren (z.B. aus Tools)
4. ⏳ Versionierung von Prompts (z.B. `v1/`, `v2/` Ordner)
5. ⏳ A/B-Testing-Framework für Prompts

## 🔗 Verwandte Änderungen

- [Documentation Cleanup](2026-01-09_documentation-cleanup.md)
- [Ingestion Refactoring](2026-01-09_ingestion-refactoring.md)
- [Graph Store Refactoring](2026-01-09_graph-store-refactoring.md)

---

**Status:** ✅ Abgeschlossen  
**Reviewed by:** -  
**Deployed:** Pending Railway

