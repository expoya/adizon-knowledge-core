"""
Property Sanitizer for CRM Entities.

Handles property sanitization for Neo4j storage, including:
- Lookup field flattening (id + name)
- JSON serialization for complex types
- Type validation
"""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class PropertySanitizer:
    """
    Sanitizes CRM properties for Neo4j storage.
    
    Neo4j properties must be primitives (str, int, float, bool) or arrays thereof.
    This class handles the conversion of complex CRM data structures.
    """
    
    def sanitize(self, props: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize properties for Neo4j storage.
        
        Args:
            props: Raw properties from CRM
            
        Returns:
            Sanitized properties (primitives only)
            
        Example:
            >>> sanitizer = PropertySanitizer()
            >>> raw = {"Owner": {"id": "123", "name": "John"}, "Amount": 1000}
            >>> sanitizer.sanitize(raw)
            {"owner_id": "123", "owner_name": "John", "amount": 1000}
        """
        sanitized = {}
        
        for key, value in props.items():
            if value is None:
                continue  # Skip None values
                
            elif isinstance(value, dict):
                # Handle lookup fields (Zoho: {"id": "...", "name": "..."})
                lookup_props = self._handle_lookup_field(key, value)
                sanitized.update(lookup_props)
                
            elif isinstance(value, list):
                # Handle arrays
                sanitized_list = self._handle_list_field(key, value)
                if sanitized_list is not None:
                    sanitized[key] = sanitized_list
                    
            elif isinstance(value, (str, int, float, bool)):
                # Primitive: keep as-is
                sanitized[key] = value
                
            else:
                # Unknown type: convert to string
                logger.debug(f"Converting unknown type {type(value)} to string for field {key}")
                sanitized[key] = str(value)
                
        return sanitized
    
    def _handle_lookup_field(self, key: str, value: dict) -> Dict[str, str]:
        """
        Extract id and name from Zoho lookup field.
        
        Zoho lookup fields have structure: {"id": "...", "name": "..."}
        We flatten this to: {field_id: "...", field_name: "..."}
        
        Args:
            key: Field name (e.g., "Owner", "Account_Name")
            value: Lookup field dict
            
        Returns:
            Flattened properties
        """
        result = {}
        
        # Extract ID if present
        if "id" in value:
            field_id_key = f"{key.lower()}_id"
            result[field_id_key] = str(value["id"])
            
        # Extract name if present
        if "name" in value:
            field_name_key = f"{key.lower()}_name"
            result[field_name_key] = str(value["name"])
        
        # If neither id nor name, serialize whole dict
        if not result:
            logger.debug(f"Lookup field {key} has no 'id' or 'name', serializing to JSON")
            result[key] = json.dumps(value)
            
        return result
    
    def _handle_list_field(self, key: str, value: list) -> Any:
        """
        Handle list/array fields.
        
        Args:
            key: Field name
            value: List value
            
        Returns:
            Sanitized list or None if empty
        """
        if not value:
            return None
            
        # Check if list contains dicts
        if value and isinstance(value[0], dict):
            # Array of dicts: serialize to JSON string
            logger.debug(f"Serializing array of dicts for field {key}")
            return json.dumps(value)
        else:
            # Primitive array: keep as-is
            return value

