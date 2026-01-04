# Ontology Configuration Guide

## Übersicht

Adizon Knowledge Core verwendet YAML-basierte Ontologien für mandantenfähige Entity-Extraktion. Die Ontologie definiert, welche Node-Types und Relationship-Types das LLM extrahieren darf.

## Dateistruktur

```
backend/app/config/ontology_voltage.yaml    # Backend (falls lokal)
trooper_worker/config/ontology_voltage.yaml # Worker (Produktion)
```

## YAML Schema

```yaml
domain_name: "Firmenname"
description: "Kurze Beschreibung der Domain"

node_types:
  - name: "NODE_TYPE_NAME"       # UPPERCASE, keine Leerzeichen
    description: "Beschreibung für LLM"

relationship_types:
  - name: "RELATIONSHIP_NAME"    # UPPERCASE_SNAKE_CASE
    description: "Beschreibung für LLM"
```

## Beispiel: Voltage Solutions (PV-Branche)

```yaml
domain_name: "Voltage Solutions"
description: "B2B Photovoltaics provider handling sales, projects, and maintenance."

node_types:
  - name: "ORGANIZATION"
    description: "Companies, Suppliers, Clients involved in business."

  - name: "PERSON"
    description: "Individuals, employees, or contact persons."

  - name: "DEAL"
    description: "Sales opportunities, offers, or potential contracts."

  - name: "PROJECT"
    description: "Physical installation projects and construction sites."

  - name: "PRODUCT"
    description: "PV hardware like modules, inverters, batteries."

  - name: "LOCATION"
    description: "Physical addresses or roof locations."

relationship_types:
  - name: "WORKS_FOR"
    description: "Employment or affiliation relationship."

  - name: "HAS_DEAL"
    description: "Company owns a sales opportunity."

  - name: "INVOLVES_PRODUCT"
    description: "Deal or Project includes specific hardware."

  - name: "LOCATED_AT"
    description: "Entity is located at a physical address."

  - name: "CONTACT_FOR"
    description: "Person is the contact for an organization or project."

  - name: "PART_OF_PROJECT"
    description: "Deal or Product is associated with a project."

  - name: "SUPPLIES"
    description: "Organization supplies products or services."

  - name: "MANAGES"
    description: "Person manages a project, deal, or organization."
```

## Neue Ontologie erstellen

### 1. YAML-Datei anlegen

```bash
# Für neuen Mandanten
cp trooper_worker/config/ontology_voltage.yaml \
   trooper_worker/config/ontology_<mandant>.yaml
```

### 2. Domain anpassen

```yaml
domain_name: "Mandant Name"
description: "Branchenbeschreibung"
```

### 3. Node-Types definieren

Überlege:
- Welche Entitäten sind relevant?
- Welche Informationen sollen verknüpft werden?
- Was fragt der User typischerweise?

**Best Practices:**
- 4-8 Node-Types (nicht zu viele!)
- Klare, eindeutige Namen
- Aussagekräftige Beschreibungen für LLM

### 4. Relationships definieren

Überlege:
- Wie hängen die Entities zusammen?
- Welche Beziehungen sind geschäftsrelevant?

**Best Practices:**
- Verben im Namen (WORKS_FOR, MANAGES, SUPPLIES)
- Richtung beachten (von → zu)
- Beschreibung erklärt Semantik

### 5. Environment konfigurieren

```bash
# In Worker .env
ONTOLOGY_PATH=config/ontology_<mandant>.yaml
```

### 6. Worker neu starten

```bash
docker-compose restart adizon-worker
```

---

## Technische Details

### SchemaFactory

Die Klasse `SchemaFactory` (in `services/schema_factory.py`) verarbeitet die YAML:

```python
factory = SchemaFactory("config/ontology_voltage.yaml")
models = factory.get_dynamic_models()

# Enthält:
# - DynamicNode: Pydantic Model mit Literal["ORGANIZATION", "PERSON", ...]
# - DynamicRelationship: Pydantic Model mit Literal["WORKS_FOR", ...]
# - ExtractionResult: Container mit nodes[] und relationships[]
```

### LLM System Prompt

`factory.get_system_instruction()` generiert:

```markdown
# Domain: Voltage Solutions
B2B Photovoltaics provider handling sales, projects, and maintenance.

## Available Node Types
Extract entities using ONLY these node types:

- **ORGANIZATION**: Companies, Suppliers, Clients involved in business.
- **PERSON**: Individuals, employees, or contact persons.
...

## Available Relationship Types
Connect nodes using ONLY these relationship types:

- **WORKS_FOR**: Employment or affiliation relationship.
...

## Extraction Rules
1. Only use the node types and relationship types defined above.
2. Each node must have a unique, descriptive name.
3. Relationships must connect nodes of appropriate types.
4. Include relevant properties when available in the source text.
5. Do not invent information not present in the source.
```

### Structured Output

Das LLM wird mit `.with_structured_output(ExtractionResult)` konfiguriert:

```python
structured_llm = llm.with_structured_output(ExtractionResult)
result = structured_llm.invoke(prompt)

# result.nodes: List[DynamicNode]
# result.relationships: List[DynamicRelationship]
```

Durch Literal-Types kann das LLM nur definierte Types wählen.

---

## Branchenbeispiele

### Rechtsanwaltskanzlei

```yaml
domain_name: "Legal Practice"
description: "Law firm handling cases, clients, and court proceedings."

node_types:
  - name: "CLIENT"
    description: "Mandanten der Kanzlei"
  - name: "CASE"
    description: "Rechtsfälle und Aktenzeichen"
  - name: "LAWYER"
    description: "Anwälte und Rechtsberater"
  - name: "COURT"
    description: "Gerichte und Instanzen"
  - name: "DOCUMENT"
    description: "Verträge, Urteile, Schriftsätze"

relationship_types:
  - name: "REPRESENTS"
    description: "Anwalt vertritt Mandanten"
  - name: "FILED_AT"
    description: "Fall eingereicht bei Gericht"
  - name: "REFERENCES"
    description: "Dokument bezieht sich auf Fall"
```

### IT-Unternehmen

```yaml
domain_name: "IT Services"
description: "IT service provider managing projects, systems, and support."

node_types:
  - name: "CUSTOMER"
    description: "Kunden und Auftraggeber"
  - name: "PROJECT"
    description: "IT-Projekte und Implementierungen"
  - name: "SYSTEM"
    description: "Software, Server, Infrastruktur"
  - name: "EMPLOYEE"
    description: "Mitarbeiter und Consultants"
  - name: "TICKET"
    description: "Support-Anfragen und Incidents"

relationship_types:
  - name: "OPERATES"
    description: "Kunde betreibt System"
  - name: "ASSIGNED_TO"
    description: "Mitarbeiter ist Projekt zugewiesen"
  - name: "AFFECTS"
    description: "Ticket betrifft System"
```

---

## Tipps

1. **Weniger ist mehr:** Starte mit 5-6 Node-Types, erweitere bei Bedarf

2. **Beschreibungen sind wichtig:** Das LLM nutzt sie zur Klassifizierung

3. **Konsistente Namenskonventionen:**
   - Nodes: `UPPERCASE` (PERSON, PROJECT)
   - Relationships: `UPPERCASE_SNAKE_CASE` (WORKS_FOR, PART_OF)

4. **Testen:** Lade ein Testdokument hoch und prüfe extrahierte Entities im Wissens-Garten

5. **Iterieren:** Passe Beschreibungen an, wenn LLM falsch klassifiziert
