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

# =============================================================================
# Security: Prototype Pollution Prevention
# =============================================================================

# Keys that could enable prototype pollution attacks if processed
# These are JavaScript/JSON security concerns that should be blocked
DANGEROUS_KEYS = {
    '__proto__',       # Direct prototype access
    'constructor',     # Constructor access
    'prototype',       # Prototype chain access
    '__defineGetter__',
    '__defineSetter__',
    '__lookupGetter__',
    '__lookupSetter__',
}


class PropertySanitizer:
    """
    Sanitizes CRM properties for Neo4j storage.
    
    Neo4j properties must be primitives (str, int, float, bool) or arrays thereof.
    This class handles the conversion of complex CRM data structures.
    """
    
    def sanitize(self, props: Dict[str, Any] | None) -> Dict[str, Any]:
        """
        Sanitize properties for Neo4j storage.

        Args:
            props: Raw properties from CRM (can be None)

        Returns:
            Sanitized properties (primitives only), empty dict if props is None

        Example:
            >>> sanitizer = PropertySanitizer()
            >>> raw = {"Owner": {"id": "123", "name": "John"}, "Amount": 1000}
            >>> sanitizer.sanitize(raw)
            {"owner_id": "123", "owner_name": "John", "amount": 1000}
        """
        # Handle None or empty input gracefully
        if not props:
            return {}

        sanitized = {}

        for key, value in props.items():
            # Security: Skip dangerous keys (prototype pollution prevention)
            if key in DANGEROUS_KEYS:
                logger.warning(f"Blocked dangerous key: '{key}' (prototype pollution prevention)")
                continue

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
            # Security: Filter dangerous keys before serializing
            safe_value = {k: v for k, v in value.items() if k not in DANGEROUS_KEYS}
            result[key] = json.dumps(safe_value)

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

        # Filter out None values before checking types
        # This prevents issues when first element is None but later elements are dicts
        non_none_values = [v for v in value if v is not None]

        if not non_none_values:
            # All elements were None
            return None

        # Check if list contains dicts (check first non-None element)
        if isinstance(non_none_values[0], dict):
            # Array of dicts: serialize to JSON string
            logger.debug(f"Serializing array of dicts for field {key}")
            return json.dumps(non_none_values)
        else:
            # Primitive array: return non-None values
            return non_none_values

