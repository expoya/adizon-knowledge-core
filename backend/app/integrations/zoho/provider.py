"""
Zoho CRM Provider Implementation.

Clean orchestration layer that delegates to specialized modules.
"""

import logging
from typing import Any, Dict, List, Optional

from app.core.interfaces.crm import CRMProvider
from app.integrations.zoho.books_client import ZohoBooksClient
from app.integrations.zoho.books_processors import process_books_invoice, process_books_subscription
from app.integrations.zoho.client import ZohoAPIError, ZohoClient
from app.integrations.zoho.email_fetcher import fetch_all_emails_for_entities, process_email_record
from app.integrations.zoho.fetchers import fetch_via_coql, fetch_via_rest_api, fetch_users_via_api
from app.integrations.zoho.processors import process_user_record, process_zoho_record
from app.integrations.zoho.queries import search_live_facts as execute_live_facts_query
from app.integrations.zoho.schema import (
    SCHEMA_MAPPING,
    get_all_entity_types,
    get_schema_config,
    is_books_api_module,
    is_rest_api_module,
    is_special_api_module,
)

logger = logging.getLogger(__name__)


class ZohoCRMProvider(CRMProvider):
    """
    Zoho CRM integration - Clean orchestration layer.
    
    Delegates to specialized modules:
    - schema.py: Schema configuration
    - fetchers.py: Data fetching (COQL + REST API)
    - processors.py: Data processing
    - queries.py: Live facts queries
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        api_base_url: str = "https://www.zohoapis.eu",
        books_organization_id: Optional[str] = None,
    ):
        """Initialize Zoho CRM provider."""
        self.client = ZohoClient(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            api_base_url=api_base_url,
        )
        
        # Initialize Books client if organization_id is provided
        self.books_client = None
        if books_organization_id:
            self.books_client = ZohoBooksClient(
                zoho_client=self.client,
                organization_id=books_organization_id,
                api_base_url=api_base_url
            )
            logger.info(f"ZohoCRMProvider initialized with Books support (org_id: {books_organization_id})")
        else:
            logger.info("ZohoCRMProvider initialized (CRM only, no Books)")

    def check_connection(self) -> bool:
        """
        Verifies Zoho CRM connection.
        
        Returns True if client is initialized. Actual connection 
        verification happens during first API call (lazy validation).
        """
        logger.info("🔍 Checking Zoho CRM connection...")
        
        try:
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
        
        Args:
            query: COQL query string
            
        Returns:
            Query results (data field from response)
        """
        logger.debug(f"⚡ Executing COQL: {query}")
        
        try:
            response = await self.client.post(
                "/crm/v6/coql",
                json={"select_query": query}
            )
            
            data = response.get("data", [])
            logger.debug(f"  ✅ Query returned {len(data)} records")
            
            return data
            
        except ZohoAPIError as e:
            logger.warning(f"⚠️ COQL query failed | Query: {query} | Error: {str(e)}")
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
        
        Orchestrates fetching and processing for all entity types.
        
        Args:
            entity_types: List of entity types to fetch, or None for all
        
        Returns:
            List of processed records ready for graph ingestion
        """
        if entity_types is None:
            entity_types = get_all_entity_types()
        
        logger.info(f"📥 Fetching skeleton data with graph schema")
        logger.info(f"  Entity types: {entity_types}")
        
        results = []
        
        # Collect Accounts and Contacts for later Email fetching
        accounts_data = []
        contacts_data = []
        
        for entity_type in entity_types:
            try:
                # Get schema configuration
                config = get_schema_config(entity_type)
                module_name = config["module_name"]
                label = config["label"]
                fields = config["fields"].copy()
                relations = config.get("relations", [])
                
                logger.info(f"  📋 Processing {entity_type} (module: {module_name}, label: {label})...")
                
                # === SPECIAL CASE: Users via dedicated API ===
                if is_special_api_module(entity_type):
                    users = await fetch_users_via_api(self.client)
                    for user in users:
                        results.append(process_user_record(user, label))
                    continue
                
                # === SPECIAL CASE: Books API (Invoices, Subscriptions) ===
                if is_books_api_module(entity_type):
                    if not self.books_client:
                        logger.warning(f"    ⚠️ Books module '{entity_type}' requested but ZOHO_BOOKS_ORGANIZATION_ID not configured")
                        continue
                    
                    # Fetch from Books API
                    if entity_type == "BooksInvoices":
                        data = await self.books_client.fetch_all_invoices(max_pages=999)
                        for record in data:
                            results.append(process_books_invoice(record, label))
                    elif entity_type == "BooksSubscriptions":
                        data = await self.books_client.fetch_all_subscriptions(max_pages=999)
                        for record in data:
                            results.append(process_books_subscription(record, label))
                    else:
                        logger.warning(f"    ⚠️ Unknown Books module: {entity_type}")
                        continue
                    
                    if data:
                        logger.info(f"    ✅ Processed {len(data)} {entity_type}")
                    else:
                        logger.warning(f"    ⚠️ No records found for {entity_type}")
                    
                    continue
                
                # === FETCH DATA: REST API or COQL ===
                if is_rest_api_module(entity_type):
                    # Finance/Email modules use REST API
                    data = await fetch_via_rest_api(
                        self.client,
                        module_name,
                        fields,
                        limit=200,  # Max 200 per page for REST API
                        max_pages=999  # Fetch all pages (will stop when no more data)
                    )
                else:
                    # Regular CRM modules use COQL
                    where_clause = "id is not null"
                    
                    # Special filter for Leads: Only import Leads created after 2024-04-01
                    if module_name == "Leads":
                        where_clause = "id is not null AND Created_Time > '2024-04-01T00:00:00+00:00'"
                        logger.info(f"    📅 Applying Leads filter: Created_Time > 2024-04-01 (prevents importing 117k old leads)")
                    
                    data = await fetch_via_coql(
                        self.client,
                        module_name,
                        fields,
                        where_clause=where_clause,
                        limit=2000,  # Zoho COQL max: 2,000 records per query
                        max_pages=999  # Fetch all pages with pagination (OFFSET-based)
                    )
                
                # === CHECK DATA ===
                if not data:
                    logger.warning(f"    ⚠️ No records found for {entity_type} (module: {module_name})")
                    continue
                
                # === COLLECT ACCOUNTS & CONTACTS FOR EMAIL FETCHING ===
                if module_name == "Accounts":
                    accounts_data = data
                elif module_name == "Contacts":
                    contacts_data = data
                
                # === PROCESS RECORDS ===
                for record in data:
                    processed = process_zoho_record(record, label, fields, relations)
                    results.append(processed)
                
                logger.info(f"    ✅ Processed {len(data)} {entity_type}")
                
            except KeyError:
                logger.warning(f"⚠️ Unknown entity type '{entity_type}'. Skipping.")
                continue
                
            except Exception as e:
                logger.error(f"❌ Error processing {entity_type}: {e}", exc_info=True)
                continue
        
        # === FETCH EMAILS AS RELATED LISTS ===
        if accounts_data or contacts_data:
            logger.info(f"📧 Fetching Emails for Accounts & Contacts (Related Lists)...")
            
            try:
                emails = await fetch_all_emails_for_entities(
                    self.client,
                    accounts=accounts_data,
                    contacts=contacts_data,
                    limit_per_entity=200  # Max 200 emails per Account/Contact
                )
                
                # Process emails
                for email in emails:
                    processed = process_email_record(email, label="Email")
                    results.append(processed)
                
                logger.info(f"  ✅ Processed {len(emails)} Emails from Related Lists")
                
            except Exception as e:
                logger.error(f"  ❌ Error fetching emails: {e}", exc_info=True)
        
        logger.info(f"✅ Total skeleton data fetched: {len(results)} records")
        
        return results
    
    async def search_live_facts(self, entity_id: str, query_context: str) -> str:
        """
        Retrieves live facts about a Zoho entity.
        
        Delegates to queries module for actual implementation.
        
        Args:
            entity_id: Zoho record ID (with "zoho_" prefix)
            query_context: Context about what information is needed
            
        Returns:
            Formatted Markdown string with entity facts
        """
        return await execute_live_facts_query(self.client, entity_id, query_context)

    def get_provider_name(self) -> str:
        """Returns provider name."""
        return "Zoho CRM"

    def get_available_modules(self) -> List[str]:
        """
        Returns available Zoho CRM modules.
        
        Returns:
            List of module names
        """
        return [
            "Users",
            "Accounts",
            "Contacts",
            "Leads",
            "Deals",
            "Events",
            "Tasks",
            "Notes",
            "Invoices",
            "Subscriptions",
            "Emails",
        ]

    async def close(self):
        """Closes the underlying HTTP client."""
        await self.client.close()

