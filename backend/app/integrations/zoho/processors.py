"""
Data Processing Logic for Zoho CRM Records.

Extracts properties and relationships from raw Zoho API responses.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def extract_name_from_record(
    record: Dict[str, Any],
    fields: List[str],
    label: str
) -> str:
    """
    Extracts display name from a Zoho record.
    
    Handles different field patterns: First_Name/Last_Name, Account_Name, Deal_Name, etc.
    
    Args:
        record: Raw Zoho record
        fields: List of available fields
        label: Entity label (for fallback)
        
    Returns:
        Display name string
    """
    # Name field logic
    if "Last_Name" in fields and "First_Name" in fields:
        first = record.get("First_Name", "")
        last = record.get("Last_Name", "")
        
        # Filter out "None" as string and None values
        if first in [None, "None", ""]:
            first = ""
        if last in [None, "None", ""]:
            last = ""
        
        # Build name without "None" prefix
        full_name = f"{first} {last}".strip()
        return full_name if full_name else f"Unknown {label}"
        
    elif "Account_Name" in fields:
        return record.get("Account_Name", f"Unknown {label}")
    elif "Deal_Name" in fields:
        return record.get("Deal_Name", f"Unknown {label}")
    elif "Subject" in fields:
        return record.get("Subject", f"Unknown {label}")
    elif "Name" in fields:
        return record.get("Name", f"Unknown {label}")
    else:
        return f"Unknown {label}"


def extract_properties_from_record(
    record: Dict[str, Any],
    fields: List[str],
    label: str
) -> Dict[str, Any]:
    """
    Extracts properties from a Zoho record.
    
    Handles:
    - Scalar fields (strings, numbers, dates)
    - Lookup fields (extracts both ID and name)
    - Name extraction
    
    Args:
        record: Raw Zoho record
        fields: List of available fields
        label: Entity label
        
    Returns:
        Properties dict
    """
    properties = {"zoho_id": record.get("id")}
    
    # Extract display name
    properties["name"] = extract_name_from_record(record, fields, label)
    
    # Add other scalar fields
    for field in fields:
        if field in ["id", "First_Name", "Last_Name", "Account_Name", "Deal_Name", "Subject", "Name"]:
            continue  # Already processed
        
        value = record.get(field)
        
        # Handle lookup fields: Store as flat properties AND create relations
        if isinstance(value, dict):
            # Lookup field: Extract ID and name for RAG/Embeddings
            lookup_id = value.get("id")
            
            # Robust name extraction with multiple fallbacks
            lookup_name = (
                value.get("name") or 
                value.get("full_name") or 
                value.get("Full_Name") or
                value.get("first_name") or
                value.get("last_name") or
                value.get("email") or
                value.get("Email") or
                value.get("Account_Name") or
                value.get("Deal_Name") or
                value.get("Subject")
            )
            
            # For Owner fields: Try combining first + last name
            if not lookup_name and "Owner" in field:
                first_name = value.get("first_name", "")
                last_name = value.get("last_name", "")
                if first_name or last_name:
                    lookup_name = f"{first_name} {last_name}".strip()
            
            if lookup_id:
                properties[f"{field.lower()}_id"] = str(lookup_id)
            if lookup_name:
                properties[f"{field.lower()}_name"] = str(lookup_name)
            else:
                # ZOHO COQL LIMITATION: Lookup fields only contain ID
                # This is expected behavior - name will be resolved via graph relationship
                logger.debug(f"Lookup field '{field}' only has ID (COQL limitation). Will resolve via relationship. ID: {lookup_id}")
        elif value:
            # Scalar field: store directly
            properties[field.lower()] = value
    
    return properties


def extract_relations_from_record(
    record: Dict[str, Any],
    relation_configs: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Extracts relationships from a Zoho record.
    
    Args:
        record: Raw Zoho record
        relation_configs: List of relation configurations from schema
        
    Returns:
        List of relation dicts
    """
    relations = []
    
    for rel_config in relation_configs:
        field_name = rel_config["field"]
        field_value = record.get(field_name)
        
        if not field_value:
            continue
        
        # Extract ID from lookup field (dict with "id" key)
        target_id = None
        target_name = None
        
        if isinstance(field_value, dict):
            target_id = field_value.get("id")
            
            # Robust name extraction with multiple fallbacks
            target_name = (
                field_value.get("name") or 
                field_value.get("full_name") or 
                field_value.get("Full_Name") or
                field_value.get("first_name") or
                field_value.get("last_name") or
                field_value.get("email") or
                field_value.get("Email") or
                field_value.get("Account_Name") or
                field_value.get("Deal_Name") or
                field_value.get("Subject")
            )
            
            # For Owner fields: Try combining first + last name
            if not target_name and "Owner" in field_name:
                first_name = field_value.get("first_name", "")
                last_name = field_value.get("last_name", "")
                if first_name or last_name:
                    target_name = f"{first_name} {last_name}".strip()
            
            # Note: We don't log here since we already logged in properties extraction
            
        elif isinstance(field_value, str):
            target_id = field_value
        
        if target_id:
            relations.append({
                "target_id": f"zoho_{target_id}",
                "edge_type": rel_config["edge"],
                "target_label": rel_config["target_label"],
                "direction": rel_config["direction"]
            })
    
    return relations


def process_zoho_record(
    record: Dict[str, Any],
    label: str,
    fields: List[str],
    relation_configs: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Processes a single Zoho record into our graph schema format.
    
    Args:
        record: Raw Zoho API record
        label: Target node label
        fields: List of available fields
        relation_configs: Relation configurations from schema
        
    Returns:
        Processed record dict with source_id, label, properties, relations
    """
    return {
        "source_id": f"zoho_{record.get('id')}",
        "label": label,
        "properties": extract_properties_from_record(record, fields, label),
        "relations": extract_relations_from_record(record, relation_configs)
    }


def process_user_record(user: Dict[str, Any], label: str) -> Dict[str, Any]:
    """
    Processes a Zoho User record (special case).
    
    Users come from /users API with different field structure.
    
    Args:
        user: Raw user record from /users API
        label: Target node label
        
    Returns:
        Processed record dict
    """
    return {
        "source_id": f"zoho_{user.get('id')}",
        "label": label,
        "properties": {
            "name": user.get("full_name") or user.get("name", "Unknown User"),
            "email": user.get("email"),
            "zoho_id": user.get("id")
        },
        "relations": []
    }

