"""
Zoho Books API Client.

Handles authentication and API requests for Zoho Books.
Uses the same OAuth token as CRM but different endpoints.
"""

import logging
from typing import Any, Dict, List, Optional

from app.integrations.zoho.client import ZohoAPIError, ZohoClient

logger = logging.getLogger(__name__)


class ZohoBooksClient:
    """
    Zoho Books API Client.
    
    Wraps ZohoClient with Books-specific logic:
    - organization_id management
    - Books API endpoints (/books/v3/...)
    - Books-specific error handling
    """

    def __init__(
        self,
        zoho_client: ZohoClient,
        organization_id: str,
        api_base_url: str = "https://www.zohoapis.eu"
    ):
        """
        Initialize Zoho Books client.
        
        Args:
            zoho_client: Existing ZohoClient instance (reuses OAuth token)
            organization_id: Zoho Books organization ID (required for all requests)
            api_base_url: Zoho API base URL (region-specific)
        """
        self.client = zoho_client
        self.organization_id = organization_id
        self.api_base_url = api_base_url.rstrip("/")
        
        logger.info(f"ZohoBooksClient initialized (org_id: {organization_id})")

    async def get_invoices(
        self, 
        page: int = 1, 
        per_page: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Fetches invoices from Zoho Books.
        
        Args:
            page: Page number (1-based)
            per_page: Records per page (max 200)
            
        Returns:
            List of invoice records
        """
        endpoint = "/books/v3/invoices"
        params = {
            "organization_id": self.organization_id,
            "page": page,
            "per_page": min(per_page, 200)  # Books max 200 per page
        }
        
        try:
            response = await self.client.get(endpoint, params=params)
            invoices = response.get("invoices", [])
            
            logger.debug(f"  📄 Books Invoices page {page}: {len(invoices)} records")
            
            return invoices
            
        except ZohoAPIError as e:
            logger.warning(f"  ⚠️ Books Invoices API error on page {page}: {e}")
            return []
        except Exception as e:
            logger.error(f"  ❌ Unexpected error fetching Books Invoices: {e}", exc_info=True)
            return []

    async def fetch_all_invoices(
        self, 
        max_pages: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetches all invoices with pagination.
        
        Args:
            max_pages: Maximum pages to fetch (safety limit)
            
        Returns:
            List of all invoice records
        """
        logger.info(f"    🔄 Fetching Books Invoices (max {max_pages} pages)...")
        
        all_invoices = []
        page = 1
        
        while page <= max_pages:
            invoices = await self.get_invoices(page=page, per_page=200)
            
            if not invoices:
                logger.debug(f"    📄 Page {page}: No more invoices")
                break
            
            all_invoices.extend(invoices)
            logger.info(f"    📄 Page {page}: Fetched {len(invoices)} invoices (Total: {len(all_invoices)})")
            
            # If we got less than 200, we're on the last page
            if len(invoices) < 200:
                logger.info(f"    ✅ Last page reached ({len(invoices)} < 200)")
                break
            
            page += 1
            
            # Rate limiting (100 calls/min = 0.6s per call)
            import asyncio
            await asyncio.sleep(0.6)
        
        logger.info(f"    ✅ Total Books Invoices fetched: {len(all_invoices)}")
        
        return all_invoices

    async def get_contacts(
        self, 
        page: int = 1, 
        per_page: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Fetches contacts (customers) from Zoho Books.
        
        Note: In Zoho Books, customers are called "contacts" 
        (not to be confused with CRM Contacts).
        
        Args:
            page: Page number (1-based)
            per_page: Records per page (max 200)
            
        Returns:
            List of contact records with zcrm_account_id for CRM mapping
        """
        endpoint = "/books/v3/contacts"
        params = {
            "organization_id": self.organization_id,
            "page": page,
            "per_page": min(per_page, 200)  # Books max 200 per page
        }
        
        try:
            response = await self.client.get(endpoint, params=params)
            contacts = response.get("contacts", [])
            
            logger.debug(f"  📇 Books Contacts page {page}: {len(contacts)} records")
            
            return contacts
            
        except ZohoAPIError as e:
            logger.warning(f"  ⚠️ Books Contacts API error on page {page}: {e}")
            return []
        except Exception as e:
            logger.error(f"  ❌ Unexpected error fetching Books Contacts: {e}", exc_info=True)
            return []

    async def fetch_all_contacts(
        self, 
        max_pages: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetches all contacts (customers) with pagination.
        
        Args:
            max_pages: Maximum pages to fetch (safety limit)
            
        Returns:
            List of all contact records
        """
        logger.info(f"    🔄 Fetching Books Contacts (max {max_pages} pages)...")
        
        all_contacts = []
        page = 1
        
        while page <= max_pages:
            contacts = await self.get_contacts(page=page, per_page=200)
            
            if not contacts:
                logger.debug(f"    📇 Page {page}: No more contacts")
                break
            
            all_contacts.extend(contacts)
            logger.info(f"    📇 Page {page}: Fetched {len(contacts)} contacts (Total: {len(all_contacts)})")
            
            # If we got less than 200, we're on the last page
            if len(contacts) < 200:
                logger.info(f"    ✅ Last page reached ({len(contacts)} < 200)")
                break
            
            page += 1
            
            # Rate limiting (100 calls/min = 0.6s per call)
            import asyncio
            await asyncio.sleep(0.6)
        
        logger.info(f"    ✅ Total Books Contacts fetched: {len(all_contacts)}")
        
        return all_contacts

    async def build_customer_to_account_mapping(self) -> Dict[str, str]:
        """
        Builds a mapping from Books customer_id to CRM Account ID.
        
        This uses the zcrm_account_id field which is populated when
        Zoho Books is integrated with Zoho CRM.
        
        Returns:
            Dict mapping Books contact_id -> CRM account_id
            Example: {"123456": "987654", ...}
        """
        logger.info("    🔗 Building Books Customer → CRM Account mapping...")
        
        contacts = await self.fetch_all_contacts(max_pages=100)
        
        mapping = {}
        mapped_count = 0
        unmapped_count = 0
        
        # DEBUG: Log first contact to see all available fields
        if contacts:
            logger.debug(f"    🔍 DEBUG: First contact fields: {list(contacts[0].keys())}")
            logger.debug(f"    🔍 DEBUG: Sample contact: {contacts[0]}")
        
        for contact in contacts:
            contact_id = contact.get("contact_id")
            contact_name = contact.get("contact_name", "Unknown")
            
            # Try multiple possible field names for CRM Account ID
            zcrm_account_id = (
                contact.get("zcrm_account_id") or
                contact.get("crm_account_id") or
                contact.get("account_id") or  # Might conflict with Books account_id!
                contact.get("zcrm_account") or
                None
            )
            
            if contact_id:
                if zcrm_account_id:
                    # Strip any prefix if Zoho adds one
                    # Usually it's just the numeric ID, but being safe
                    account_id = str(zcrm_account_id).strip()
                    mapping[str(contact_id)] = account_id
                    mapped_count += 1
                    logger.debug(f"      ✅ Mapped: Books Contact {contact_id} ({contact_name}) → CRM Account {account_id}")
                else:
                    unmapped_count += 1
                    # Only log first few unmapped for debugging
                    if unmapped_count <= 3:
                        logger.debug(f"      ⚠️ No CRM mapping for Books Contact {contact_id} ({contact_name})")
        
        logger.info(f"    ✅ Mapping complete: {mapped_count} mapped, {unmapped_count} unmapped")
        
        if unmapped_count > 0:
            logger.warning(
                f"    ⚠️ {unmapped_count} Books customers have no CRM Account mapping. "
                "This is normal if they were created only in Books or CRM sync is not enabled."
            )
        
        return mapping

    def close(self):
        """
        Close is handled by the parent ZohoClient.
        This is a no-op for Books client.
        """
        pass

