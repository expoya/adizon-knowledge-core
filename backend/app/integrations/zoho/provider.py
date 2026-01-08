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
        Verifies Zoho CRM connection by fetching modules list.
        
        Returns:
            True if connection successful (status 200), False otherwise
        """
        logger.info("🔍 Checking Zoho CRM connection...")
        
        try:
            # Get or create event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Run async request
            response = loop.run_until_complete(
                self.client.get("/crm/v6/settings/modules")
            )
            
            # Check if modules are in response
            success = "modules" in response
            
            if success:
                logger.info("✅ Zoho CRM connection successful")
            else:
                logger.warning("⚠️ Zoho CRM connection check: unexpected response format")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Zoho connection check failed: {e}")
            return False

    def execute_raw_query(self, query: str) -> Any:
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
            # Get or create event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Execute query
            response = loop.run_until_complete(
                self.client.post(
                    "/crm/v6/coql",
                    json={"select_query": query}
                )
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

    def fetch_skeleton_data(
        self, 
        entity_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetches comprehensive master data from Zoho CRM with smart field resolution.
        
        This method automatically adapts to the Zoho schema by:
        1. Fetching field metadata for each module
        2. Resolving field names from candidate lists
        3. Building queries only with valid fields
        4. Gracefully handling missing fields
        
        Args:
            entity_types: Zoho module names. Defaults to:
                         ["Users", "Accounts", "Contacts", "Leads", "Deals", 
                          "Events", "Invoices", "Subscriptions"]
            
        Returns:
            List of entity records with standardized format:
            {
                "source_id": "zoho_{id}",
                "name": "...",
                "type": "{Type}",
                "email": "...",  # Optional
                "related_to": "zoho_{parent_id}",  # Optional
                "relation_type": "HAS_DEAL",  # Optional
                "amount": 1000,  # Optional (Deals, Invoices)
                "stage": "Negotiation",  # Optional (Deals)
                "status": "Active",  # Optional (Events, Subscriptions)
                "total": 500,  # Optional (Subscriptions, Invoices)
                "start_time": "2024-01-01",  # Optional (Events)
            }
        """
        if entity_types is None:
            entity_types = [
                "Users",
                "Accounts", 
                "Contacts",
                "Leads",
                "Deals",
                "Events",
                "Invoices",
                "Subscriptions"
            ]
        
        logger.info(f"📥 Fetching skeleton data with smart field resolution")
        logger.info(f"  Entity types: {entity_types}")
        
        # Get or create event loop for async operations
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Module configurations with field candidates
        MODULE_CONFIGS = {
            "Users": {
                "name_candidates": ["full_name", "name", "Full_Name"],
                "email_candidates": ["email", "Email"],
                "module_name": "Users",
                "relation_type": None,
            },
            "Accounts": {
                "name_candidates": ["Account_Name", "Name"],
                "email_candidates": [],
                "related_candidates": ["Owner"],
                "relation_type": "OWNED_BY",
                "module_name": "Accounts",
            },
            "Contacts": {
                "name_candidates": ["Last_Name", "First_Name"],  # Will be combined
                "email_candidates": ["Email"],
                "related_candidates": ["Account_Name", "Account"],
                "relation_type": "WORKS_AT",
                "module_name": "Contacts",
            },
            "Leads": {
                "name_candidates": ["Last_Name", "First_Name"],  # Will be combined
                "email_candidates": ["Email"],
                "related_candidates": ["Owner"],
                "relation_type": "OWNED_BY",
                "module_name": "Leads",
            },
            "Deals": {
                "name_candidates": ["Deal_Name", "Name"],
                "amount_candidates": ["Amount", "Total", "Grand_Total"],
                "stage_candidates": ["Stage"],
                "related_candidates": ["Account_Name", "Leads", "Contact_Name"],
                "relation_type": "HAS_DEAL",
                "module_name": "Deals",
            },
            "Events": {
                "name_candidates": ["Name", "Event_Title"],
                "status_candidates": ["Status"],
                "start_time_candidates": ["Event_Start_Time", "Start_DateTime"],
                "related_candidates": ["Lead", "Account", "Contact_Name"],
                "relation_type": "HAS_EVENT",
                "module_name": "calendlyforzohocrm__Calendly_Events",  # Custom module
            },
            "Subscriptions": {
                "name_candidates": ["Name", "Subscription_Name"],
                "total_candidates": ["Total", "Amount"],
                "status_candidates": ["Status"],
                "related_candidates": ["Account", "Account_Name"],
                "relation_type": "HAS_SUBSCRIPTION",
                "module_name": "Subscriptions__s",  # Custom module
            },
            "Invoices": {
                "name_candidates": ["Subject", "Name", "Invoice_Number"],
                "total_candidates": ["Total", "Grand_Total", "Sub_Total"],
                "status_candidates": ["Status"],
                "related_candidates": ["Account", "Account_Name", "Contact_Name"],
                "relation_type": "HAS_INVOICE",
                "module_name": "Zoho_Books",  # Custom module
            },
        }
        
        results = []
        
        for entity_type in entity_types:
            if entity_type not in MODULE_CONFIGS:
                logger.warning(f"⚠️ Unknown entity type: {entity_type}")
                continue
            
            config = MODULE_CONFIGS[entity_type]
            module_name = config["module_name"]
            
            logger.info(f"  📋 Processing {entity_type} (module: {module_name})...")
            
            try:
                # Resolve fields for this module
                resolved_fields = {}
                
                # Resolve name field(s)
                if entity_type in ["Contacts", "Leads"]:
                    # Special case: name from First + Last
                    first_name = loop.run_until_complete(
                        self._resolve_best_field(module_name, ["First_Name"])
                    )
                    last_name = loop.run_until_complete(
                        self._resolve_best_field(module_name, ["Last_Name"])
                    )
                    resolved_fields["first_name"] = first_name
                    resolved_fields["last_name"] = last_name
                else:
                    name_field = loop.run_until_complete(
                        self._resolve_best_field(module_name, config["name_candidates"])
                    )
                    resolved_fields["name"] = name_field
                
                # Resolve optional fields
                if "email_candidates" in config and config["email_candidates"]:
                    email_field = loop.run_until_complete(
                        self._resolve_best_field(module_name, config["email_candidates"])
                    )
                    resolved_fields["email"] = email_field
                
                if "amount_candidates" in config:
                    amount_field = loop.run_until_complete(
                        self._resolve_best_field(module_name, config["amount_candidates"])
                    )
                    resolved_fields["amount"] = amount_field
                
                if "stage_candidates" in config:
                    stage_field = loop.run_until_complete(
                        self._resolve_best_field(module_name, config["stage_candidates"])
                    )
                    resolved_fields["stage"] = stage_field
                
                if "status_candidates" in config:
                    status_field = loop.run_until_complete(
                        self._resolve_best_field(module_name, config["status_candidates"])
                    )
                    resolved_fields["status"] = status_field
                
                if "total_candidates" in config:
                    total_field = loop.run_until_complete(
                        self._resolve_best_field(module_name, config["total_candidates"])
                    )
                    resolved_fields["total"] = total_field
                
                if "start_time_candidates" in config:
                    start_time_field = loop.run_until_complete(
                        self._resolve_best_field(module_name, config["start_time_candidates"])
                    )
                    resolved_fields["start_time"] = start_time_field
                
                if "related_candidates" in config:
                    related_field = loop.run_until_complete(
                        self._resolve_best_field(module_name, config["related_candidates"])
                    )
                    resolved_fields["related"] = related_field
                
                # Log resolved schema
                logger.info(f"    🔧 Resolved schema for {entity_type}:")
                for key, value in resolved_fields.items():
                    if value:
                        logger.info(f"      {key} -> {value}")
                
                # Check if we have minimum required fields
                if entity_type in ["Contacts", "Leads"]:
                    if not (resolved_fields.get("first_name") or resolved_fields.get("last_name")):
                        logger.warning(f"    ⚠️ Skipping {entity_type}: No name fields found")
                        continue
                else:
                    if not resolved_fields.get("name"):
                        logger.warning(f"    ⚠️ Skipping {entity_type}: No name field found")
                        continue
                
                # Build COQL query
                select_fields = ["id"]
                
                if entity_type in ["Contacts", "Leads"]:
                    if resolved_fields.get("first_name"):
                        select_fields.append(resolved_fields["first_name"])
                    if resolved_fields.get("last_name"):
                        select_fields.append(resolved_fields["last_name"])
                else:
                    if resolved_fields.get("name"):
                        select_fields.append(resolved_fields["name"])
                
                if resolved_fields.get("email"):
                    select_fields.append(resolved_fields["email"])
                if resolved_fields.get("amount"):
                    select_fields.append(resolved_fields["amount"])
                if resolved_fields.get("stage"):
                    select_fields.append(resolved_fields["stage"])
                if resolved_fields.get("status"):
                    select_fields.append(resolved_fields["status"])
                if resolved_fields.get("total"):
                    select_fields.append(resolved_fields["total"])
                if resolved_fields.get("start_time"):
                    select_fields.append(resolved_fields["start_time"])
                if resolved_fields.get("related"):
                    select_fields.append(resolved_fields["related"])
                
                query = f"SELECT {', '.join(select_fields)} FROM {module_name} LIMIT 200"
                logger.debug(f"    Query: {query}")
                
                # Execute query
                data = self.execute_raw_query(query)
                
                # Process records
                for record in data:
                    entity = {
                        "source_id": f"zoho_{record.get('id')}",
                        "type": entity_type.rstrip("s") if entity_type not in ["Events", "Invoices", "Subscriptions"] else entity_type,
                    }
                    
                    # Extract name
                    if entity_type in ["Contacts", "Leads"]:
                        first = record.get(resolved_fields.get("first_name"), "")
                        last = record.get(resolved_fields.get("last_name"), "")
                        entity["name"] = f"{first} {last}".strip() or f"Unknown {entity_type}"
                    else:
                        entity["name"] = record.get(resolved_fields.get("name"), f"Unknown {entity_type}")
                    
                    # Extract optional fields
                    if resolved_fields.get("email"):
                        entity["email"] = record.get(resolved_fields["email"])
                    
                    if resolved_fields.get("amount"):
                        entity["amount"] = record.get(resolved_fields["amount"])
                    
                    if resolved_fields.get("stage"):
                        entity["stage"] = record.get(resolved_fields["stage"])
                    
                    if resolved_fields.get("status"):
                        entity["status"] = record.get(resolved_fields["status"])
                    
                    if resolved_fields.get("total"):
                        entity["total"] = record.get(resolved_fields["total"])
                    
                    if resolved_fields.get("start_time"):
                        entity["start_time"] = record.get(resolved_fields["start_time"])
                    
                    # Extract relationship
                    if resolved_fields.get("related"):
                        related_value = record.get(resolved_fields["related"])
                        if related_value:
                            # Handle both dict (lookup) and string formats
                            if isinstance(related_value, dict) and related_value.get("id"):
                                entity["related_to"] = f"zoho_{related_value['id']}"
                                entity["relation_type"] = config["relation_type"]
                            elif isinstance(related_value, str):
                                entity["related_to"] = f"zoho_{related_value}"
                                entity["relation_type"] = config["relation_type"]
                    
                    results.append(entity)
                
                logger.info(f"    ✅ Fetched {len(data)} {entity_type}")
                
            except Exception as e:
                logger.error(f"❌ Error fetching {entity_type}: {e}", exc_info=True)
                continue
        
        logger.info(f"✅ Total skeleton data fetched: {len(results)} records")
        
        return results

    def search_live_facts(self, entity_id: str, query_context: str) -> str:
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
            query = f"SELECT Name, Grund, Status FROM Einw_nde WHERE Lead.id = '{zoho_id}' LIMIT 50"
            einwaende = self.execute_raw_query(query)
            
            if einwaende:
                section = ["### 🛡️ Einwände\n"]
                for obj in einwaende:
                    name = obj.get("Name", "N/A")
                    grund = obj.get("Grund", "N/A")
                    status = obj.get("Status", "N/A")
                    section.append(f"- **{name}**: {grund} (Status: {status})")
                sections.append("\n".join(section))
                
        except Exception as e:
            logger.warning(f"⚠️ Einwände query failed: {e}")
            sections.append("### 🛡️ Einwände\n*(Query failed)*")
        
        # === B) Calendly Events ===
        try:
            # Try Lead relation first
            query = f"SELECT Name, Event_Start_Time, Status FROM calendlyforzohocrm__Calendly_Events WHERE Lead.id = '{zoho_id}' LIMIT 20"
            calendly = self.execute_raw_query(query)
            
            # Fallback: Try Account relation
            if not calendly:
                query = f"SELECT Name, Event_Start_Time, Status FROM calendlyforzohocrm__Calendly_Events WHERE Account.id = '{zoho_id}' LIMIT 20"
                calendly = self.execute_raw_query(query)
            
            if calendly:
                section = ["### 📅 Calendly Events\n"]
                for event in calendly:
                    name = event.get("Name", "N/A")
                    start_time = event.get("Event_Start_Time", "N/A")
                    status = event.get("Status", "N/A")
                    section.append(f"- **{name}**: {start_time} (Status: {status})")
                sections.append("\n".join(section))
                
        except Exception as e:
            logger.warning(f"⚠️ Calendly query failed: {e}")
            sections.append("### 📅 Calendly Events\n*(Query failed)*")
        
        # === C) Deals ===
        try:
            # Try Lead relation first
            query = f"SELECT Deal_Name, Amount, Stage, Closing_Date FROM Deals WHERE Leads.id = '{zoho_id}' LIMIT 50"
            deals = self.execute_raw_query(query)
            
            # Fallback: Try Account relation
            if not deals:
                query = f"SELECT Deal_Name, Amount, Stage, Closing_Date FROM Deals WHERE Account_Name.id = '{zoho_id}' LIMIT 50"
                deals = self.execute_raw_query(query)
            
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
        try:
            query = f"SELECT Name, Total, Status FROM Subscriptions__s WHERE Account.id = '{zoho_id}' LIMIT 20"
            finance = self.execute_raw_query(query)
            
            if finance:
                section = ["### 🧾 Finance (Subscriptions)\n"]
                for sub in finance:
                    name = sub.get("Name", "N/A")
                    total = sub.get("Total", 0)
                    status = sub.get("Status", "N/A")
                    section.append(f"- **{name}**: €{total} (Status: {status})")
                sections.append("\n".join(section))
                
        except Exception as e:
            logger.warning(f"⚠️ Finance query failed: {e}")
            sections.append("### 🧾 Finance\n*(Query failed)*")
        
        # === Build final response ===
        if not sections:
            return f"""
# Live Facts for Entity: {entity_id}

No data found across all modules.

Query Context: {query_context}
"""
        
        result = f"""
# Live Facts for Entity: {entity_id}

Query Context: _{query_context}_

{chr(10).join(sections)}

---
*Data source: Zoho CRM*
"""
        
        logger.info(f"✅ Live facts compiled: {len(sections)} sections")
        
        return result

    def get_provider_name(self) -> str:
        """Returns provider name."""
        return "Zoho CRM"

    def get_available_modules(self) -> List[str]:
        """
        Returns available Zoho CRM modules.
        
        Returns:
            List of module names
        """
        try:
            # Get or create event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Fetch modules
            response = loop.run_until_complete(
                self.client.get("/crm/v6/settings/modules")
            )
            
            modules = response.get("modules", [])
            module_names = [
                mod.get("api_name") 
                for mod in modules 
                if mod.get("api_name") and not mod.get("api_name").startswith("__")
            ]
            
            logger.info(f"✅ Found {len(module_names)} modules")
            
            return module_names
            
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch modules: {e}")
            return []

    async def close(self):
        """Closes the underlying HTTP client."""
        await self.client.close()
