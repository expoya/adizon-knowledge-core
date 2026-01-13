# Changelog: Chat Persistence, UI Redesign & Company Context

**Datum:** 2026-01-13
**Typ:** Feature / Refactoring
**Bereich:** Frontend + Backend

## 🎯 Ziele

1. Chat-Verläufe sollen beim Navigieren erhalten bleiben
2. Multi-Chat-Support wie bei ChatGPT
3. UI-Redesign mit einheitlicher Sidebar
4. LLM mit Unternehmenskontext briefen können
5. Chat-Memory für Folgefragen

---

## ✨ Änderungen

### 1. Chat Persistence mit Zustand

**Neues State Management:**
- Zustand Store mit localStorage Persist-Middleware
- Chats bleiben auch nach Browser-Reload erhalten
- Storage Key: `adizon-chat-storage`

**Neue Dateien:**
```
frontend/src/
├── types/chat.ts           # TypeScript Interfaces
└── stores/chatStore.ts     # Zustand Store mit Persist
```

**Store Features:**
- `chats[]` - Liste aller Chat-Sessions
- `activeChatId` - Aktuell ausgewählter Chat
- `createChat()` - Neuen Chat erstellen
- `deleteChat()` - Chat löschen
- `addMessage()` - Nachricht hinzufügen
- Auto-Naming nach erster User-Nachricht

### 2. UI Redesign - ChatGPT-Style Sidebar

**Vorher:**
- Separate Navigation-Sidebar + Chat-Sidebar
- Zwei Spalten auf Desktop

**Nachher:**
- Einheitliche Sidebar im ChatGPT-Style
- Logo oben
- "Neuer Chat" Button
- Chat-Liste (scrollbar)
- Upload & Explorer unten
- Footer mit "Sovereign AI RAG"

**Layout-Struktur:**
```
┌─────────────────────────────────────────────┐
│ [Logo] Adizon Knowledge Core                │
├─────────────────────────────────────────────┤
│ [+ Neuer Chat]                              │
├─────────────────────────────────────────────┤
│ 💬 Chat 1                              [🗑] │
│ 💬 Chat 2                              [🗑] │
│ 💬 Chat 3                              [🗑] │
│ ...                                         │
├─────────────────────────────────────────────┤
│ 📤 Upload                                   │
│ 🌐 Explorer                                 │
├─────────────────────────────────────────────┤
│ ✨ Sovereign AI RAG                         │
└─────────────────────────────────────────────┘
```

**Gelöschte Dateien:**
- `frontend/src/components/ChatSidebar.tsx` (in Layout.tsx integriert)

### 3. Chat Memory für Folgefragen

**Problem:** LLM verstand keine Folgefragen wie "Was kostet das?" oder "Erzähl mir mehr darüber"

**Lösung:**
- `_format_chat_history()` Funktion in `chat_workflow.py`
- Letzte 6 Messages (3 Runden) werden dem LLM übergeben
- Prompt erweitert mit `{chat_history}` Placeholder

**Backend-Änderungen:**
```python
def _format_chat_history(messages: List[AnyMessage]) -> str:
    # Formatiert: "Benutzer: ...\nAssistent: ..."
    # Max 500 Zeichen pro Assistenten-Nachricht
    # Letzte 6 Messages (3 Runden)
```

### 4. Company Context aus MinIO

**Feature:** LLM kann mit Unternehmenskontext gebrieft werden

**Konfiguration:**
```env
COMPANY_CONTEXT_MINIO_PATH=config/company_context.md
```

**MinIO-Struktur:**
```
knowledge-documents/
├── documents/              # Hochgeladene Dokumente
├── ontology/
│   └── ontology.yaml       # Knowledge Graph Schema
└── config/
    └── company_context.md  # NEU: Unternehmenskontext
```

**Features:**
- Markdown-Format für einfache Pflege
- 5-Minuten-Cache (TTL) für Performance
- Graceful Fallback wenn nicht vorhanden
- Template unter `backend/app/prompts/company_context_template.md`

**Template-Struktur:**
```markdown
# Unternehmenskontext

## Über das Unternehmen
Name, Branche, Standort...

## Produkte & Services
...

## Kommunikationsstil
Tonalität, Ansprache, Dos/Don'ts...

## Wichtige Begriffe
Interne Terminologie...
```

### 5. Cleanup: Doppeltes Prompts-Verzeichnis

**Problem:** Zwei Prompt-Verzeichnisse existierten
- `backend/prompts/` (alt, unbenutzt)
- `backend/app/prompts/` (aktuell, korrekt)

**Lösung:**
- `backend/prompts/` gelöscht
- Alle Imports verwenden `from app.prompts import ...`
- Changelog-Pfade korrigiert

---

## 📁 Datei-Änderungen

### Frontend

| Aktion | Datei | Beschreibung |
|--------|-------|--------------|
| NEU | `src/types/chat.ts` | Chat & Message Interfaces |
| NEU | `src/stores/chatStore.ts` | Zustand Store mit Persist |
| EDIT | `src/components/Layout.tsx` | Unified Sidebar, Chat-Management integriert |
| EDIT | `src/pages/ChatPage.tsx` | Store statt useState |
| EDIT | `src/App.tsx` | Route `/chat/:chatId` hinzugefügt |
| DEL | `src/components/ChatSidebar.tsx` | In Layout integriert |
| NPM | `package.json` | `zustand` hinzugefügt |

### Backend

| Aktion | Datei | Beschreibung |
|--------|-------|--------------|
| EDIT | `app/core/config.py` | `COMPANY_CONTEXT_MINIO_PATH` Config |
| EDIT | `app/graph/chat_workflow.py` | `get_company_context()`, `_format_chat_history()` |
| EDIT | `app/prompts/answer_generation.txt` | `{company_context}`, `{chat_history}` |
| NEU | `app/prompts/company_context_template.md` | Template für Unternehmenskontext |
| DEL | `prompts/` | Doppeltes Verzeichnis entfernt |

---

## 🔧 Konfiguration

### Neue Environment Variables

```env
# Company Context (optional)
COMPANY_CONTEXT_MINIO_PATH=config/company_context.md
```

### MinIO Setup

1. Erstelle `company_context.md` basierend auf Template
2. Lade hoch nach: `knowledge-documents/config/company_context.md`
3. Backend lädt automatisch beim nächsten Request (mit 5-Min-Cache)

---

## 🧪 Tests

**Chat Persistence:**
- ✅ Chat erstellen, Nachricht senden
- ✅ Browser-Tab schließen und öffnen → Chat erhalten
- ✅ Zwischen Chats wechseln
- ✅ Chat löschen mit Bestätigung

**Chat Memory:**
- ✅ "Wer ist Max Mustermann?" → Antwort
- ✅ "Was sind seine Kontaktdaten?" → Versteht Kontext

**Company Context:**
- ✅ Ohne MinIO-File → Graceful Fallback
- ✅ Mit MinIO-File → Kontext wird geladen
- ✅ Cache funktioniert (kein wiederholtes Laden)

---

## 📊 Impact

### Performance
- Zustand: Minimal overhead, localStorage sync
- Company Context: 5-Min-Cache, kein Impact auf Response Time
- Chat History: Max 6 Messages, truncated auf 500 chars

### Bundle Size
- +1 Package: `zustand` (~3KB gzipped)
- Insgesamt: Minimal

---

## 🔗 Commits

1. `133259f` - feat: Add chat persistence with multi-chat support and chat memory
2. `006cca7` - feat: Add company context for LLM customization + cleanup

---

**Status:** ✅ Abgeschlossen
**Deployed:** Railway (Production)
