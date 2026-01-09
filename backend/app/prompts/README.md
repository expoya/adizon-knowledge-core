# Prompt Management

Dieser Ordner enthält alle System-Prompts für den Adizon Knowledge Core Agent.

## 📁 Struktur

```
prompts/
├── __init__.py                      # Prompt Loader Utility
├── README.md                        # Diese Datei
├── intent_classification.txt       # Router: Intent Detection
├── sql_generation.txt              # SQL Node: Query Generation
└── answer_generation.txt           # Generator: Final Answer Creation
```

## 🎯 Verwendung

### Im Code laden

```python
from prompts import get_prompt

# Lade einen Prompt
intent_prompt = get_prompt("intent_classification")

# Verwende mit Platzhaltern
formatted_prompt = intent_prompt.format(query="Was sind unsere Top-Kunden?")
```

### Prompt neu laden (bei Änderungen)

```python
from prompts import PromptLoader

# Einzelner Prompt
PromptLoader.reload("intent_classification")

# Alle Prompts
PromptLoader.reload()
```

### Verfügbare Prompts auflisten

```python
from prompts import PromptLoader

available = PromptLoader.list_available()
print(available)
# ['answer_generation', 'intent_classification', 'sql_generation']
```

## 🔧 Prompts bearbeiten

1. **Öffne die entsprechende `.txt` Datei**
2. **Bearbeite den Prompt-Text** (unterstützt `{placeholder}` Syntax)
3. **Speichere die Datei**
4. **Restart des Servers** oder `PromptLoader.reload()` verwenden

## ✅ Vorteile

- **Sicherheit**: Prompts können nicht versehentlich Code überschreiben
- **Übersichtlichkeit**: Prompts sind getrennt von Business Logic
- **Wartbarkeit**: Einfaches Testen und Iterieren
- **Versionierung**: Git kann Prompt-Änderungen sauber tracken
- **Caching**: Prompts werden beim Start geladen (Performance)

## 📝 Prompt-Format

Alle Prompts unterstützen Python `.format()` Platzhalter:

```txt
Du bist ein Assistent.

BENUTZERANFRAGE:
{query}

ANTWORT:
```

Verwendung:
```python
prompt = get_prompt("my_prompt")
formatted = prompt.format(query="Hallo Welt")
```

## 🚨 Wichtige Hinweise

- **Keine Code-Ausführung** in Prompts
- **UTF-8 Encoding** verwenden
- **Platzhalter** konsistent benennen
- **Kommentare** mit `#` wenn nötig
- **Tests schreiben** für kritische Prompts

