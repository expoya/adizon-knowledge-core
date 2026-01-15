"""
Data Processing Logic for Twenty CRM Records.

Extracts properties and relationships from raw Twenty API responses.
Handles nested field structures and target relationships.
"""

import logging
from typing import Any, Dict, List, Optional

from app.integrations.twenty.schema import get_schema_config, has_targets

logger = logging.getLogger(__name__)


def get_nested_value(data: Dict[str, Any], path: str) -> Any:
    """
    Gets a value from a nested dictionary using dot notation.

    Args:
        data: Dictionary to traverse
        path: Dot-separated path (e.g., "name.firstName")

    Returns:
        Value at path or None if not found
    """
    keys = path.split(".")
    value = data

    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None

        if value is None:
            return None

    return value


def extract_properties_from_record(
    record: Dict[str, Any],
    entity_type: str,
) -> Dict[str, Any]:
    """
    Extracts properties from a Twenty record.

    Handles nested fields by flattening them to our graph schema.

    Args:
        record: Raw Twenty record
        entity_type: Entity type (e.g., "people", "companies")

    Returns:
        Flattened properties dict
    """
    config = get_schema_config(entity_type)
    field_mappings = config["fields"]
    name_template = config.get("name_template", "{name}")

    properties = {"twenty_id": record.get("id")}

    # Extract all configured fields
    for source_path, target_key in field_mappings.items():
        if source_path == "id":
            continue  # Already stored as twenty_id

        value = get_nested_value(record, source_path)

        if value is not None and value != "":
            # Convert micros to decimal for currency fields
            if target_key.endswith("_micros") and isinstance(value, (int, float)):
                # Store both micros and decimal value
                properties[target_key] = value
                decimal_key = target_key.replace("_micros", "")
                properties[decimal_key] = value / 1_000_000
            else:
                properties[target_key] = value

    # Build display name from template
    properties["name"] = _build_name(properties, name_template, entity_type)

    return properties


def _build_name(
    properties: Dict[str, Any],
    template: str,
    entity_type: str,
) -> str:
    """
    Builds display name from properties using template.

    Args:
        properties: Extracted properties
        template: Name template (e.g., "{first_name} {last_name}")
        entity_type: Entity type for fallback

    Returns:
        Display name string
    """
    try:
        # Extract template fields
        import re
        fields = re.findall(r"\{(\w+)\}", template)

        # Check if all fields are present
        values = {}
        for field in fields:
            value = properties.get(field, "")
            if value in [None, "None", ""]:
                value = ""
            values[field] = str(value)

        # Build name
        name = template.format(**values).strip()

        # Clean up multiple spaces
        name = " ".join(name.split())

        if name:
            return name

    except (KeyError, ValueError):
        pass

    # Fallback
    return f"Unknown {entity_type}"


def extract_relations_from_record(
    record: Dict[str, Any],
    entity_type: str,
    properties: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Extracts relationships from a Twenty record.

    Args:
        record: Raw Twenty record
        entity_type: Entity type
        properties: Already extracted properties

    Returns:
        List of relation dicts
    """
    config = get_schema_config(entity_type)
    relation_configs = config.get("relations", [])
    relations = []

    for rel_config in relation_configs:
        field_name = rel_config["field"]

        # Get target ID from properties (already extracted)
        target_key = field_name[0].lower() + field_name[1:]  # camelCase
        if target_key.endswith("Id"):
            # Convert to snake_case for properties lookup
            prop_key = _camel_to_snake(target_key)
        else:
            prop_key = target_key

        target_id = properties.get(prop_key) or record.get(field_name)

        if target_id:
            relations.append({
                "target_id": f"twenty_{target_id}",
                "edge_type": rel_config["edge"],
                "target_label": rel_config["target_label"],
                "direction": rel_config["direction"],
            })

    return relations


def extract_target_relations(
    record: Dict[str, Any],
    entity_type: str,
) -> List[Dict[str, Any]]:
    """
    Extracts target relationships from Notes/Tasks.

    Twenty uses noteTargets/taskTargets arrays to link to multiple entities.

    Args:
        record: Raw Twenty record
        entity_type: Entity type ("notes" or "tasks")

    Returns:
        List of relation dicts
    """
    if not has_targets(entity_type):
        return []

    config = get_schema_config(entity_type)
    target_field = config.get("target_field", "")
    targets = record.get(target_field, [])

    if not targets:
        return []

    relations = []
    edge_type = "HAS_NOTE" if entity_type == "notes" else "HAS_TASK"

    for target in targets:
        # Check each possible target type
        if target.get("personId"):
            relations.append({
                "target_id": f"twenty_{target['personId']}",
                "edge_type": edge_type,
                "target_label": "Contact",
                "direction": "INCOMING",
            })

        if target.get("companyId"):
            relations.append({
                "target_id": f"twenty_{target['companyId']}",
                "edge_type": edge_type,
                "target_label": "Account",
                "direction": "INCOMING",
            })

        if target.get("opportunityId"):
            relations.append({
                "target_id": f"twenty_{target['opportunityId']}",
                "edge_type": edge_type,
                "target_label": "Deal",
                "direction": "INCOMING",
            })

    return relations


def _camel_to_snake(name: str) -> str:
    """Converts camelCase to snake_case."""
    import re
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def process_twenty_record(
    record: Dict[str, Any],
    entity_type: str,
) -> Dict[str, Any]:
    """
    Processes a single Twenty record into our graph schema format.

    Args:
        record: Raw Twenty API record
        entity_type: Entity type (e.g., "people", "companies")

    Returns:
        Processed record dict with source_id, label, properties, relations
    """
    config = get_schema_config(entity_type)
    label = config["label"]

    # Extract properties
    properties = extract_properties_from_record(record, entity_type)

    # Extract standard relations
    relations = extract_relations_from_record(record, entity_type, properties)

    # Extract target relations for Notes/Tasks
    target_relations = extract_target_relations(record, entity_type)
    relations.extend(target_relations)

    return {
        "source_id": f"twenty_{record.get('id')}",
        "label": label,
        "properties": properties,
        "relations": relations,
    }
