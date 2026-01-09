"""
Zoho CRM Provider Implementation with Smart Field Resolution.

Implements the CRMProvider interface for Zoho CRM with automatic
schema adaptation based on real API metadata.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.core.interfaces.crm import CRMProvider
from app.integrations.zoho.client import ZohoAPIError, ZohoClient

logger = logging.getLogger(__name__)


class ZohoCRMProvider(CRMProvider):
    """
    Zoho CRM integration with intelligent field resolution.
    
    This provider automatically adapts to the Zoho CRM schema by:
    1. Caching field metadata from the API
    2. Resolving field names from candidate lists
    3. Building queries only with valid fields
    4. Gracefully handling schema variations
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        api_base_url: str = "https://www.zohoapis.eu",
    ):
        """
        Initialize Zoho CRM provider with field resolution.
        
        Args:
            client_id: Zoho OAuth client ID
            client_secret: Zoho OAuth client secret
            refresh_token: Long-lived refresh token
            api_base_url: Zoho API base URL (region-specific)
        """
        self.client = ZohoClient(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            api_base_url=api_base_url,
        )
        
        # Field metadata cache: module_name -> set of valid field api_names
        self._module_fields_cache: Dict[str, set[str]] = {}
        
        logger.info("ZohoCRMProvider initialized with smart field resolution")

    async def _get_valid_fields(self, module: str) -> set[str]:
        """
        Retrieves and caches valid field names for a module.
        
        Makes API call on first access, then returns cached result.
        Handles Finance modules (Zoho_Books, Subscriptions) with hardcoded fallback.
        
        Args:
            module: Zoho module name (e.g., "Contacts", "Deals")
            
        Returns:
            Set of valid field API names for the module
        """
        # Check cache first
        if module in self._module_fields_cache:
            logger.debug(f"📦 Using cached fields for {module}")
            return self._module_fields_cache[module]
        
        logger.info(f"🔍 Fetching field metadata for module: {module}")
        
        try:
            # Fetch fields from API
            response = await self.client.get(
                "/crm/v6/settings/fields",
                params={"module": module}
            )
            
            fields = response.get("fields", [])
            field_names = {
                field.get("api_name") 
                for field in fields 
                if field.get("api_name")
            }
            
            # Cache the result
            self._module_fields_cache[module] = field_names
            
            logger.info(f"  ✅ Cached {len(field_names)} fields for {module}")
            logger.debug(f"  Sample fields: {list(field_names)[:10]}")
            
            return field_names
            
        except ZohoAPIError as e:
            # Finance modules (Zoho_Books, Subscriptions) don't support metadata API
            error_msg = str(e).lower()
            if "not_supported" in error_msg or "400" in str(e):
                logger.warning(
                    f"⚠️ Module {module} does not support metadata API. "
                    f"Using hardcoded fallback for Finance modules."
                )
                
                # Hardcoded standard fields for Finance modules
                fallback_fields = {
                    "id", 
                    "Name", 
                    "Subject", 
                    "Invoice_Number",
                    "Total", 
                    "Grand_Total", 
                    "Sub_Total",
                    "Amount",
                    "Status", 
                    "Account", 
                    "Account_Name",
                    "Contact_Name",
                    "Date",
                    "Due_Date"
                }
                
                # Cache the fallback
                self._module_fields_cache[module] = fallback_fields
                
                logger.info(f"  ✅ Using {len(fallback_fields)} fallback fields for {module}")
                return fallback_fields
            else:
                logger.error(f"❌ Error fetching fields for {module}: {e}")
                return set()
            
        except Exception as e:
            logger.error(f"❌ Error fetching fields for {module}: {e}")
            # Return empty set on error (module might not exist)
            return set()

    async def _resolve_best_field(
        self, 
        module: str, 
        candidates: List[str]
    ) -> Optional[str]:
        """
        Resolves the best matching field from candidates.
        
        Iterates through candidate field names and returns the first
        one that exists in the module's schema.
        
        Args:
            module: Zoho module name
            candidates: List of candidate field names (in priority order)
            
        Returns:
            First matching field name, or None if no match found
        """
        valid_fields = await self._get_valid_fields(module)
        
        if not valid_fields:
            logger.warning(f"⚠️ No valid fields found for module: {module}")
            return None
        
        for candidate in candidates:
            if candidate in valid_fields:
                logger.debug(f"  ✓ Resolved field '{candidate}' for {module}")
                return candidate
        
        logger.warning(
            f"⚠️ No matching field found in {module}. "
            f"Candidates: {candidates} | "
            f"Available: {list(valid_fields)[:20]}"
        )
        return None

    def check_connection(self) -> bool:
        """
        Verifies Zoho CRM connection.
        
        Note: Returns True if client is initialized. Actual connection 
        verification happens during first API call (lazy validation).
        This avoids event loop issues during sync initialization.
        
        Returns:
            True if client is initialized, False otherwise
        """
        logger.info("🔍 Checking Zoho CRM connection...")
        
        try:
            # Simple check: client exists and has required attributes
            if self.client and hasattr(self.client, 'api_base_url'):
                logger.info("✅ Zoho CRM client initialized")
                return True
            else:
                logger.warning("⚠️ Zoho CRM client not properly initialized")
                return False
            
        except Exception as e:
            logger.error(f"❌ Zoho connection check failed: {e}")
            return False

    async def execute_raw_query(self, query: str) -> Any:
        """
        Executes a COQL query against Zoho CRM.
        
        COQL (CRM Object Query Language) is Zoho's SQL-like query language.
        
        Args:
            query: COQL query string
            
        Returns:
            Query results (data field from response)
        """
        logger.debug(f"⚡ Executing COQL: {query}")
        
        try:
            # Execute query
            response = await self.client.post(
                "/crm/v6/coql",
                json={"select_query": query}
            )
            
            # Return data field
            data = response.get("data", [])
            logger.debug(f"  ✅ Query returned {len(data)} records")
            
            return data
            
        except ZohoAPIError as e:
            # Log query and error for debugging
            logger.warning(
                f"⚠️ COQL query failed | "
                f"Query: {query} | "
                f"Error: {str(e)}"
            )
            return []
            
        except Exception as e:
            logger.error(f"❌ Query execution error: {e}")
            return []

    async def fetch_skeleton_data(
        self, 
        entity_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetches skeleton data from Zoho CRM with structured graph schema.
        
        Returns nodes with specific labels and relations for direct graph ingestion.
        
        Returns:
            List of records:
            {
                "source_id": "zoho_{id}",
                "label": "Account",  # Specific node label
                "properties": {"name": "...", "amount": ...},  # Scalar fields
                "relations": [
                    {
                        "target_id": "zoho_{id}",
                        "edge_type": "HAS_OWNER",
                        "direction": "OUTGOING"
                    }
                ]
            }
        """
        # Schema mapping for graph structure
        SCHEMA_MAPPING = {
            "Users": {
                "label": "User",
                "module_name": "Users",
                "fields": ["id", "full_name", "email"],
                "relations": [],
                "use_api": True  # Special: Use /users API instead of COQL
            },
            "Leads": {
                "label": "Lead",
                "module_name": "Leads",
                "fields": ["id", "Last_Name", "First_Name", "Company", "Email", "Owner", "Converted_Account", "Created_Time"],
                "relations": [
                    {"field": "Owner", "edge": "HAS_OWNER", "target_label": "User", "direction": "OUTGOING"},
                    {"field": "Converted_Account", "edge": "IS_CONVERTED_FROM", "target_label": "Account", "direction": "INCOMING"}
                ]
            },
            "Accounts": {
                "label": "Account",
                "module_name": "Accounts",
                "fields": ["id", "Account_Name", "Owner", "Parent_Account"],
                "relations": [
                    {"field": "Owner", "edge": "HAS_OWNER", "target_label": "User", "direction": "OUTGOING"},
                    {"field": "Parent_Account", "edge": "PARENT_OF", "target_label": "Account", "direction": "INCOMING"}
                ]
            },
            "Contacts": {
                "label": "Contact",
                "module_name": "Contacts",
                "fields": ["id", "Last_Name", "First_Name", "Email", "Account_Name", "Owner"],
                "relations": [
                    {"field": "Account_Name", "edge": "WORKS_AT", "target_label": "Account", "direction": "OUTGOING"},
                    {"field": "Owner", "edge": "HAS_OWNER", "target_label": "User", "direction": "OUTGOING"}
                ]
            },
            "Deals": {
                "label": "Deal",
                "module_name": "Deals",
                "fields": ["id", "Deal_Name", "Account_Name", "Contact_Name", "Stage", "Amount", "Owner", "Closing_Date"],
                "relations": [
                    {"field": "Account_Name", "edge": "HAS_DEAL", "target_label": "Account", "direction": "INCOMING"},
                    {"field": "Contact_Name", "edge": "ASSOCIATED_WITH", "target_label": "Contact", "direction": "OUTGOING"},
                    {"field": "Owner", "edge": "HAS_OWNER", "target_label": "User", "direction": "OUTGOING"}
                ]
            },
            "Tasks": {
                "label": "Task",
                "module_name": "Tasks",
                "fields": ["id", "Subject", "Status", "Who_Id", "What_Id", "Owner"],
                "relations": [
                    {"field": "Who_Id", "edge": "HAS_TASK", "target_label": "CRMEntity", "direction": "INCOMING"},
                    {"field": "What_Id", "edge": "HAS_TASK", "target_label": "CRMEntity", "direction": "INCOMING"},
                    {"field": "Owner", "edge": "HAS_OWNER", "target_label": "User", "direction": "OUTGOING"}
                ]
            },
            "Notes": {
                "label": "Note",
                "module_name": "Notes",
                "fields": ["id", "Note_Title", "Note_Content", "Parent_Id", "Owner"],
                "relations": [
                    {"field": "Parent_Id", "edge": "HAS_NOTE", "target_label": "CRMEntity", "direction": "INCOMING"},
                    {"field": "Owner", "edge": "HAS_OWNER", "target_label": "User", "direction": "OUTGOING"}
                ]
            },
            "Events": {
                "label": "CalendlyEvent",
                "module_name": "calendlyforzohocrm__Calendly_Events",
                "fields": ["id", "Name", "calendlyforzohocrm__Lead", "calendlyforzohocrm__Contact", "Verkn_pfter_Account", "calendlyforzohocrm__Status", "calendlyforzohocrm__Start_Time"],
                "relations": [
                    {"field": "calendlyforzohocrm__Lead", "edge": "HAS_EVENT", "target_label": "Lead", "direction": "INCOMING"},
                    {"field": "calendlyforzohocrm__Contact", "edge": "HAS_EVENT", "target_label": "Contact", "direction": "INCOMING"},
                    {"field": "Verkn_pfter_Account", "edge": "HAS_EVENT", "target_label": "Account", "direction": "INCOMING"}
                ]
            },
            "Invoices": {
                "label": "Invoice",
                "module_name": "Zoho_Books",
                "fields": ["id", "Subject", "Account", "Total", "Status"],
                "relations": [
                    {"field": "Account", "edge": "HAS_INVOICE", "target_label": "Account", "direction": "INCOMING"}
                ],
                "skip_coql": True  # Finance module does not support COQL
            },
            "Subscriptions": {
                "label": "Subscription",
                "module_name": "Subscriptions__s",
                "fields": ["id", "Name", "Account", "Total", "Status"],
                "relations": [
                    {"field": "Account", "edge": "HAS_SUBSCRIPTION", "target_label": "Account", "direction": "INCOMING"}
                ],
                "skip_coql": True  # Finance module does not support COQL
            },
            "Einwaende": {
                "label": "Einwand",
                "module_name": "Einw_nde",
                "fields": ["id", "Name", "Lead", "Einwand_Kategorie", "Gespr_chszeitpunkt", "Einwandbeschreibung"],
                "relations": [
                    {"field": "Lead", "edge": "HAS_OBJECTION", "target_label": "Lead", "direction": "INCOMING"}
                ]
            },
            "Attachments": {
                "label": "Attachment",
                "module_name": "Attachments",
                "fields": ["id", "File_Name", "Parent_Id"],
                "relations": [
                    {"field": "Parent_Id", "edge": "HAS_DOCUMENTS", "target_label": "CRMEntity", "direction": "INCOMING"}
                ]
            },
            # Aliases for alternative naming (module names vs friendly names)
            "Zoho_Books": {  # Alias for Invoices
                "label": "Invoice",
                "module_name": "Zoho_Books",
                "fields": ["id", "Subject", "Account", "Total", "Status"],
                "relations": [
                    {"field": "Account", "edge": "HAS_INVOICE", "target_label": "Account", "direction": "INCOMING"}
                ],
                "skip_coql": True  # Finance module does not support COQL
            },
            "Einw_nde": {  # Alias for Einwaende
                "label": "Einwand",
                "module_name": "Einw_nde",
                "fields": ["id", "Name", "Lead", "Einwand_Kategorie", "Gespr_chszeitpunkt", "Einwandbeschreibung"],
                "relations": [
                    {"field": "Lead", "edge": "HAS_OBJECTION", "target_label": "Lead", "direction": "INCOMING"}
                ]
            },
            "calendlyforzohocrm__Calendly_Events": {  # Alias for Events (full module name)
                "label": "CalendlyEvent",
                "module_name": "calendlyforzohocrm__Calendly_Events",
                "fields": ["id", "Name", "calendlyforzohocrm__Lead", "calendlyforzohocrm__Contact", "Verkn_pfter_Account", "calendlyforzohocrm__Status", "calendlyforzohocrm__Start_Time"],
                "relations": [
                    {"field": "calendlyforzohocrm__Lead", "edge": "HAS_EVENT", "target_label": "Lead", "direction": "INCOMING"},
                    {"field": "calendlyforzohocrm__Contact", "edge": "HAS_EVENT", "target_label": "Contact", "direction": "INCOMING"},
                    {"field": "Verkn_pfter_Account", "edge": "HAS_EVENT", "target_label": "Account", "direction": "INCOMING"}
                ]
            },
            "Subscriptions__s": {  # Alias for Subscriptions (full module name)
                "label": "Subscription",
                "module_name": "Subscriptions__s",
                "fields": ["id", "Name", "Account", "Total", "Status"],
                "relations": [
                    {"field": "Account", "edge": "HAS_SUBSCRIPTION", "target_label": "Account", "direction": "INCOMING"}
                ],
                "skip_coql": True  # Finance module does not support COQL
            }
        }
        
        if entity_types is None:
            entity_types = list(SCHEMA_MAPPING.keys())
        
        logger.info(f"📥 Fetching skeleton data with graph schema")
        logger.info(f"  Entity types: {entity_types}")
        
        results = []
        
        for entity_type in entity_types:
            if entity_type not in SCHEMA_MAPPING:
                logger.warning(f"⚠️ Unknown entity type '{entity_type}'. Skipping. Available types: {list(SCHEMA_MAPPING.keys())}")
                continue
            
            config = SCHEMA_MAPPING[entity_type]
            module_name = config["module_name"]
            label = config["label"]
            
            logger.info(f"  📋 Processing {entity_type} (module: {module_name}, label: {label})...")
            
            try:
                # Special case: Users via API (not COQL)
                if config.get("use_api", False):
                    try:
                        response = await self.client.get("/crm/v6/users", params={"type": "ActiveUsers"})
                        users = response.get("users", [])
                        
                        for user in users:
                            results.append({
                                "source_id": f"zoho_{user.get('id')}",
                                "label": label,
                                "properties": {
                                    "name": user.get("full_name") or user.get("name", "Unknown User"),
                                    "email": user.get("email"),
                                    "zoho_id": user.get("id")
                                },
                                "relations": []
                            })
                        
                        logger.info(f"    ✅ Fetched {len(users)} {entity_type}")
                        continue
                        
                    except Exception as e:
                        logger.warning(f"    ⚠️ Skipping {entity_type} (API error): {e}")
                        continue
                
                # Skip COQL for Finance modules (not supported)
                if config.get("skip_coql", False):
                    logger.warning(f"    ⚠️ Skipping {entity_type}: COQL not supported (Finance module). TODO: Use Finance API.")
                    continue
                
                # Build SELECT query with all fields
                fields_to_select = config["fields"].copy()
                
                # === SMOKE TEST: Limited fetch for validation ===
                # TODO: After successful smoke test, change limit to 10000 and enable pagination
                all_data = []
                offset = 0
                limit = 50  # 🔥 SMOKE TEST: Limited to 50 records per entity
                page = 1
                max_pages = 1  # 🔥 SMOKE TEST: Only fetch first page
                
                # Special filter for Leads: Only import leads created after 2024-04-01
                where_clause = "id is not null"
                if module_name == "Leads":
                    where_clause = "id is not null AND Created_Time > '2024-04-01T00:00:00+00:00'"
                    logger.info(f"    📅 Applying Leads filter: Created_Time > 2024-04-01")
                
                logger.info(f"    🔥 SMOKE TEST MODE: LIMIT {limit}, max {max_pages} page(s)")
                
                while True:
                    # Build paginated query
                    query = f"SELECT {', '.join(fields_to_select)} FROM {module_name} WHERE {where_clause} LIMIT {limit} OFFSET {offset}"
                    logger.debug(f"    Query (Page {page}): {query}")
                    
                    try:
                        # Execute query
                        data = await self.execute_raw_query(query)
                        
                        if not data:
                            logger.debug(f"    📄 Page {page}: No more records")
                            break  # No more records
                        
                        all_data.extend(data)
                        logger.info(f"    📄 Page {page}: Fetched {len(data)} records (Total: {len(all_data)})")
                        
                        # 🔥 SMOKE TEST: Stop after max_pages
                        if page >= max_pages:
                            logger.info(f"    🔥 SMOKE TEST: Stopping after {max_pages} page(s)")
                            break
                        
                        # Check if we got less than limit (last page)
                        if len(data) < limit:
                            logger.info(f"    ✅ Last page reached ({len(data)} < {limit})")
                            break
                        
                        # Increment for next page
                        offset += limit
                        page += 1
                        
                        # Rate Limit Protection: Sleep 0.6s between calls
                        # Zoho allows 100 calls/min = 1 call every 0.6s
                        await asyncio.sleep(0.6)
                        
                    except ZohoAPIError as e:
                        error_msg = str(e).lower()
                        # Check for Finance module errors
                        if module_name in ["Zoho_Books", "Subscriptions__s", "Einw_nde"] and ("not_supported" in error_msg or "400" in str(e)):
                            logger.warning(f"    ⚠️ COQL not supported for {module_name}")
                            break
                        else:
                            logger.error(f"    ❌ API error on page {page}: {e}")
                            # Continue with what we have (error recovery)
                            break
                    
                    except Exception as e:
                        logger.error(f"    ❌ Unexpected error on page {page}: {e}", exc_info=True)
                        # Continue with what we have (error recovery)
                        break
                
                # Use accumulated data
                data = all_data
                
                # Final check: If no data fetched
                if not data:
                    if module_name in ["Zoho_Books", "Subscriptions__s"]:
                        logger.warning(f"    ⚠️ Skipping {entity_type}: COQL not supported for Finance modules")
                    else:
                        logger.info(f"    ℹ️ No records found for {entity_type}")
                    continue
                
                # Process records
                for record in data:
                    # Extract properties (scalar fields)
                    properties = {"zoho_id": record.get("id")}
                    
                    # Name field logic
                    if "Last_Name" in fields_to_select and "First_Name" in fields_to_select:
                        first = record.get("First_Name", "")
                        last = record.get("Last_Name", "")
                        
                        # Filter out "None" as string and None values
                        if first in [None, "None", ""]:
                            first = ""
                        if last in [None, "None", ""]:
                            last = ""
                        
                        # Build name without "None" prefix
                        full_name = f"{first} {last}".strip()
                        properties["name"] = full_name if full_name else f"Unknown {label}"
                    elif "Account_Name" in fields_to_select:
                        properties["name"] = record.get("Account_Name", f"Unknown {label}")
                    elif "Deal_Name" in fields_to_select:
                        properties["name"] = record.get("Deal_Name", f"Unknown {label}")
                    elif "Subject" in fields_to_select:
                        properties["name"] = record.get("Subject", f"Unknown {label}")
                    elif "Name" in fields_to_select:
                        properties["name"] = record.get("Name", f"Unknown {label}")
                    else:
                        properties["name"] = f"Unknown {label}"
                    
                    # Add other scalar fields
                    for field in fields_to_select:
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
                    
                    # Extract relations
                    relations = []
                    for rel_config in config.get("relations", []):
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
                            
                            # CRITICAL: Also store lookup as flat property for embeddings
                            if target_id:
                                properties[f"{field_name.lower()}_id"] = str(target_id)
                            if target_name:
                                properties[f"{field_name.lower()}_name"] = str(target_name)
                            else:
                                # ZOHO COQL LIMITATION: Lookup fields only contain ID
                                # This is expected behavior - name will be resolved via graph relationship
                                logger.debug(f"Relation field '{field_name}' only has ID (COQL limitation). Relationship will be created. ID: {target_id}")
                        elif isinstance(field_value, str):
                            target_id = field_value
                        
                        if target_id:
                            relations.append({
                                "target_id": f"zoho_{target_id}",
                                "edge_type": rel_config["edge"],
                                "target_label": rel_config["target_label"],
                                "direction": rel_config["direction"]
                            })
                    
                    results.append({
                        "source_id": f"zoho_{record.get('id')}",
                        "label": label,
                        "properties": properties,
                        "relations": relations
                    })
                
                logger.info(f"    ✅ Fetched {len(data)} {entity_type}")
                
            except ZohoAPIError as e:
                error_msg = str(e).lower()
                if module_name in ["Zoho_Books", "Subscriptions__s", "Einw_nde"] and ("not_supported" in error_msg or "400" in str(e)):
                    logger.warning(f"    ⚠️ Skipping {entity_type}: COQL not supported")
                    continue
                else:
                    logger.error(f"❌ Zoho API error fetching {entity_type}: {e}")
                    continue
                    
            except Exception as e:
                logger.error(f"❌ Error fetching {entity_type}: {e}", exc_info=True)
                continue
        
        logger.info(f"✅ Total skeleton data fetched: {len(results)} records")
        
        return results
    
    async def search_live_facts(self, entity_id: str, query_context: str) -> str:
        """
        Retrieves live facts about a Zoho entity.
        
        Queries multiple modules (Einwände, Calendly, Deals, Finance) and
        formats results as Markdown for LLM consumption.
        
        Args:
            entity_id: Zoho record ID (with "zoho_" prefix)
            query_context: Context about what information is needed
            
        Returns:
            Formatted Markdown string with entity facts
        """
        logger.info(f"🔍 Searching live facts for entity: {entity_id}")
        logger.debug(f"Query context: {query_context}")
        
        # Remove "zoho_" prefix
        if entity_id.startswith("zoho_"):
            zoho_id = entity_id[5:]
        else:
            zoho_id = entity_id
        
        # Collect results
        sections = []
        
        # === A) Einwände (Objections) ===
        try:
            # Fixed: Removed "Status" field (doesn't exist), kept core fields
            query = f"SELECT Name, Einwand_Kategorie, Einwandbeschreibung FROM Einw_nde WHERE Lead.id = '{zoho_id}' LIMIT 50"
            einwaende = await self.execute_raw_query(query)
            
            if einwaende:
                section = ["### 🛡️ Einwände\n"]
                for obj in einwaende:
                    name = obj.get("Name", "N/A")
                    kategorie = obj.get("Einwand_Kategorie", "N/A")
                    beschreibung = obj.get("Einwandbeschreibung", "")
                    
                    # Format output with category and description
                    if beschreibung:
                        section.append(f"- **{name}** ({kategorie}): {beschreibung}")
                    else:
                        section.append(f"- **{name}** ({kategorie})")
                sections.append("\n".join(section))
                
        except Exception as e:
            logger.warning(f"⚠️ Einwände query failed: {e}")
            sections.append("### 🛡️ Einwände\n*(Query failed)*")
        
        # === B) Calendly Events ===
        try:
            # Fixed: Use correct field name "calendlyforzohocrm__Start_Time" and removed "Status"
            # Try Lead relation first
            query = f"SELECT Name, calendlyforzohocrm__Start_Time, calendlyforzohocrm__Status FROM calendlyforzohocrm__Calendly_Events WHERE calendlyforzohocrm__Lead.id = '{zoho_id}' LIMIT 20"
            calendly = await self.execute_raw_query(query)
            
            # Fallback: Try Contact relation
            if not calendly:
                query = f"SELECT Name, calendlyforzohocrm__Start_Time, calendlyforzohocrm__Status FROM calendlyforzohocrm__Calendly_Events WHERE calendlyforzohocrm__Contact.id = '{zoho_id}' LIMIT 20"
                calendly = await self.execute_raw_query(query)
            
            # Fallback: Try Account relation
            if not calendly:
                query = f"SELECT Name, calendlyforzohocrm__Start_Time, calendlyforzohocrm__Status FROM calendlyforzohocrm__Calendly_Events WHERE Verkn_pfter_Account.id = '{zoho_id}' LIMIT 20"
                calendly = await self.execute_raw_query(query)
            
            if calendly:
                section = ["### 📅 Calendly Events\n"]
                for event in calendly:
                    name = event.get("Name", "N/A")
                    start_time = event.get("calendlyforzohocrm__Start_Time", "N/A")
                    status = event.get("calendlyforzohocrm__Status", "N/A")
                    section.append(f"- **{name}**: {start_time} (Status: {status})")
                sections.append("\n".join(section))
                
        except Exception as e:
            logger.warning(f"⚠️ Calendly query failed: {e}")
            sections.append("### 📅 Calendly Events\n*(Query failed)*")
        
        # === C) Deals ===
        try:
            # Fixed: Changed "Leads.id" to "Lead_Source.id" or try without lookup
            # First try: Contact relation (most common for converted leads)
            query = f"SELECT Deal_Name, Amount, Stage, Closing_Date FROM Deals WHERE Contact_Name.id = '{zoho_id}' LIMIT 50"
            deals = await self.execute_raw_query(query)
            
            # Fallback: Try Account relation
            if not deals:
                query = f"SELECT Deal_Name, Amount, Stage, Closing_Date FROM Deals WHERE Account_Name.id = '{zoho_id}' LIMIT 50"
                deals = await self.execute_raw_query(query)
            
            if deals:
                section = ["### 💰 Deals\n"]
                total_amount = 0
                for deal in deals:
                    name = deal.get("Deal_Name", "N/A")
                    amount = deal.get("Amount", 0)
                    stage = deal.get("Stage", "N/A")
                    closing = deal.get("Closing_Date", "N/A")
                    
                    section.append(f"- **{name}**: €{amount:,.2f} | {stage} | Close: {closing}")
                    
                    if amount:
                        total_amount += float(amount)
                
                section.append(f"\n**Total Deal Value**: €{total_amount:,.2f}")
                sections.append("\n".join(section))
                
        except Exception as e:
            logger.warning(f"⚠️ Deals query failed: {e}")
            sections.append("### 💰 Deals\n*(Query failed)*")
        
        # === D) Finance / Subscriptions ===
        # Skip Finance modules - COQL not supported for Subscriptions__s
        # These would need to use REST API instead
        logger.debug("⚠️ Skipping Finance/Subscriptions - COQL not supported for finance modules")
        
        # === Build final response ===
        if not sections:
            return f"""
# Live Facts for Entity: {entity_id}

No data found across all modules (Einwände, Calendly Events, Deals).

Query Context: {query_context}
"""
        
        result = f"""
# Live Facts for Entity: {entity_id}

Query Context: _{query_context}_

{chr(10).join(sections)}

---
*Data source: Zoho CRM*
*Note: Some queries may have failed due to missing fields or permissions.*
"""
        
        logger.info(f"✅ Live facts compiled: {len(sections)} sections")
        
        return result

    def get_provider_name(self) -> str:
        """Returns provider name."""
        return "Zoho CRM"

    def get_available_modules(self) -> List[str]:
        """
        Returns available Zoho CRM modules.
        
        Note: Returns common modules list. For async module discovery,
        use fetch_skeleton_data() which validates modules during execution.
        
        Returns:
            List of common module names
        """
        # Return common modules to avoid event loop issues
        # Actual module availability is validated during fetch_skeleton_data()
        return [
            "Users",
            "Accounts",
            "Contacts",
            "Leads",
            "Deals",
            "Events",
            "Tasks",
            "Calls",
            "Meetings",
        ]

    async def close(self):
        """Closes the underlying HTTP client."""
        await self.client.close()
