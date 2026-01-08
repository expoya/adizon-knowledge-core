"""
Zoho CRM Provider Implementation.
Implements the CRMProvider interface for Zoho CRM.
"""

import logging
from typing import Any, Dict, List, Optional

from app.core.interfaces.crm import CRMProvider
from app.integrations.zoho.client import ZohoAPIError, ZohoClient

logger = logging.getLogger(__name__)


class ZohoCRMProvider(CRMProvider):
    """
    Zoho CRM integration implementation.
    
    This is the Expoya-specific addon that implements CRM functionality
    using Zoho's API and COQL (CRM Object Query Language).
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        api_base_url: str = "https://www.zohoapis.eu",
    ):
        """
        Initialize Zoho CRM provider.
        
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
        logger.info("ZohoCRMProvider initialized")

    def check_connection(self) -> bool:
        """
        Verifies Zoho CRM connection by fetching modules list.
        
        Returns:
            True if connection successful (status 200), False otherwise
        """
        logger.info("🔍 Checking Zoho CRM connection...")
        
        try:
            # Use asyncio to run the async method
            import asyncio
            
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
        logger.info("⚡ Executing COQL query")
        logger.debug(f"Query: {query}")
        
        try:
            import asyncio
            
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
            logger.info(f"✅ Query returned {len(data)} records")
            
            return data
            
        except ZohoAPIError as e:
            # Log query and error for debugging
            logger.warning(
                f"⚠️ COQL query failed. "
                f"Query: {query} | "
                f"Error: {str(e)}"
            )
            return []
            
        except Exception as e:
            logger.error(f"❌ Query execution error: {e}")
            return []

    def fetch_skeleton_data(self, entity_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Fetches basic master data from Zoho CRM for graph import.
        
        Args:
            entity_types: Zoho module names. Defaults to ["Users", "Accounts", "Contacts", "Leads"]
            
        Returns:
            List of entity records with standardized format:
            {"source_id": "zoho_{id}", "name": "...", "type": "{Type}", ...}
        """
        if entity_types is None:
            entity_types = ["Users", "Accounts", "Contacts", "Leads"]
        
        logger.info(f"📥 Fetching skeleton data for: {entity_types}")
        
        results = []
        
        for entity_type in entity_types:
            logger.info(f"  📋 Fetching {entity_type}...")
            
            try:
                # Build COQL query based on entity type
                if entity_type == "Users":
                    query = "SELECT id, full_name, email FROM Users LIMIT 200"
                    
                    data = self.execute_raw_query(query)
                    
                    for record in data:
                        results.append({
                            "source_id": f"zoho_{record.get('id')}",
                            "name": record.get("full_name", "Unknown User"),
                            "type": "User",
                            "email": record.get("email"),
                        })
                
                elif entity_type == "Accounts":
                    query = "SELECT id, Account_Name FROM Accounts LIMIT 200"
                    
                    data = self.execute_raw_query(query)
                    
                    for record in data:
                        results.append({
                            "source_id": f"zoho_{record.get('id')}",
                            "name": record.get("Account_Name", "Unknown Account"),
                            "type": "Account",
                        })
                
                elif entity_type in ["Contacts", "Leads"]:
                    query = f"SELECT id, Last_Name, First_Name, Email FROM {entity_type} LIMIT 200"
                    
                    data = self.execute_raw_query(query)
                    
                    for record in data:
                        # Build name from First_Name + Last_Name
                        first = record.get("First_Name", "")
                        last = record.get("Last_Name", "")
                        name = f"{first} {last}".strip() or "Unknown"
                        
                        results.append({
                            "source_id": f"zoho_{record.get('id')}",
                            "name": name,
                            "type": entity_type.rstrip("s"),  # "Contacts" -> "Contact"
                            "email": record.get("Email"),
                        })
                
                else:
                    logger.warning(f"⚠️ Unknown entity type: {entity_type}")
                
                logger.info(f"    ✅ Fetched {len([r for r in results if r['type'] == entity_type.rstrip('s')])} {entity_type}")
                
            except Exception as e:
                logger.error(f"❌ Error fetching {entity_type}: {e}")
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
            zoho_id = entity_id[5:]  # Remove first 5 chars
        else:
            zoho_id = entity_id
        
        logger.debug(f"Zoho ID (cleaned): {zoho_id}")
        
        # Collect results
        sections = []
        
        # === A) Einwände (Objections) ===
        try:
            logger.debug("Querying Einwände...")
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
                logger.debug(f"  ✅ Found {len(einwaende)} Einwände")
            else:
                logger.debug("  ℹ️ No Einwände found")
                
        except Exception as e:
            logger.warning(f"⚠️ Einwände query failed: {e}")
            sections.append("### 🛡️ Einwände\n*(Debug: Query failed - Check Logs)*")
        
        # === B) Calendly Events ===
        try:
            logger.debug("Querying Calendly Events...")
            # Try Lead relation first
            query = f"SELECT Name, Event_Start_Time, Status FROM calendlyforzohocrm__Calendly_Events WHERE Lead.id = '{zoho_id}' LIMIT 20"
            calendly = self.execute_raw_query(query)
            
            # Fallback: Try Account relation
            if not calendly:
                logger.debug("  Trying Account relation...")
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
                logger.debug(f"  ✅ Found {len(calendly)} Calendly events")
            else:
                logger.debug("  ℹ️ No Calendly events found")
                
        except Exception as e:
            logger.warning(f"⚠️ Calendly query failed: {e}")
            sections.append("### 📅 Calendly Events\n*(Debug: Query failed - Check Logs)*")
        
        # === C) Deals ===
        try:
            logger.debug("Querying Deals...")
            # Try Lead relation first
            query = f"SELECT Deal_Name, Amount, Stage, Closing_Date FROM Deals WHERE Leads.id = '{zoho_id}' LIMIT 50"
            deals = self.execute_raw_query(query)
            
            # Fallback: Try Account relation
            if not deals:
                logger.debug("  Trying Account_Name relation...")
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
                logger.debug(f"  ✅ Found {len(deals)} deals")
            else:
                logger.debug("  ℹ️ No deals found")
                
        except Exception as e:
            logger.warning(f"⚠️ Deals query failed: {e}")
            sections.append("### 💰 Deals\n*(Debug: Query failed - Check Logs)*")
        
        # === D) Finance / Subscriptions ===
        try:
            logger.debug("Querying Finance/Subscriptions...")
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
                logger.debug(f"  ✅ Found {len(finance)} subscriptions")
            else:
                logger.debug("  ℹ️ No subscriptions found")
                
        except Exception as e:
            logger.warning(f"⚠️ Finance query failed: {e}")
            sections.append("### 🧾 Finance\n*(Debug: Query failed - Check Logs)*")
        
        # === Build final response ===
        if not sections:
            return f"""
# Live Facts for Entity: {entity_id}

No data found across all modules.
This could mean:
- Entity has no related records yet
- Entity ID might be incorrect
- Relations might use different field names

Query Context: {query_context}
"""
        
        result = f"""
# Live Facts for Entity: {entity_id}

Query Context: _{query_context}_

{chr(10).join(sections)}

---
*Data source: Zoho CRM | Timestamp: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        logger.info(f"✅ Live facts compiled: {len(sections)} sections")
        
        return result

    def _get_field_names(self, module: str) -> List[str]:
        """
        Retrieves field names for a specific Zoho module.
        
        Useful for debugging when queries fail due to incorrect field names.
        
        Args:
            module: Zoho module name (e.g., "Contacts", "Deals")
            
        Returns:
            List of field API names
        """
        logger.info(f"📋 Getting field names for module: {module}")
        
        try:
            import asyncio
            
            # Get or create event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Fetch fields
            response = loop.run_until_complete(
                self.client.get(
                    "/crm/v6/settings/fields",
                    params={"module": module}
                )
            )
            
            fields = response.get("fields", [])
            field_names = [field.get("api_name") for field in fields if field.get("api_name")]
            
            logger.info(f"  ✅ Found {len(field_names)} fields")
            logger.debug(f"  Field names: {', '.join(field_names[:20])}...")  # Log first 20
            
            return field_names
            
        except Exception as e:
            logger.error(f"❌ Error getting field names for {module}: {e}")
            return []

    def get_provider_name(self) -> str:
        """Returns provider name."""
        return "Zoho CRM"

    def get_available_modules(self) -> List[str]:
        """
        Returns available Zoho CRM modules.
        
        Fetches from API if possible, otherwise returns common modules.
        
        Returns:
            List of module names
        """
        logger.info("📋 Getting available Zoho modules")
        
        try:
            import asyncio
            
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
            
            logger.info(f"  ✅ Found {len(module_names)} modules")
            
            return module_names
            
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch modules from API: {e}")
            
            # Return common modules as fallback
            return [
                "Contacts",
                "Accounts",
                "Deals",
                "Leads",
                "Tasks",
                "Calls",
                "Meetings",
                "Notes",
                "Products",
                "Quotes",
            ]

    async def close(self):
        """Closes the underlying HTTP client."""
        await self.client.close()
