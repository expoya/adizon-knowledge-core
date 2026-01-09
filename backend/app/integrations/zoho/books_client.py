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

    async def get_subscriptions(
        self, 
        page: int = 1, 
        per_page: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Fetches subscriptions from Zoho Books/Billing.
        
        Args:
            page: Page number (1-based)
            per_page: Records per page (max 200)
            
        Returns:
            List of subscription records
        """
        # Note: Subscriptions might be in /billing/v1/ or /books/v3/
        # We'll try Books first, then Billing
        
        endpoint = "/books/v3/subscriptions"
        params = {
            "organization_id": self.organization_id,
            "page": page,
            "per_page": min(per_page, 200)
        }
        
        try:
            response = await self.client.get(endpoint, params=params)
            subscriptions = response.get("subscriptions", [])
            
            logger.debug(f"  📄 Books Subscriptions page {page}: {len(subscriptions)} records")
            
            return subscriptions
            
        except ZohoAPIError as e:
            # Try Billing API as fallback
            logger.debug(f"  ⚠️ Books Subscriptions not available, trying Billing API...")
            return await self._get_subscriptions_from_billing(page, per_page)
        except Exception as e:
            logger.error(f"  ❌ Unexpected error fetching Subscriptions: {e}", exc_info=True)
            return []

    async def _get_subscriptions_from_billing(
        self, 
        page: int = 1, 
        per_page: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Fallback: Fetch subscriptions from Zoho Billing API.
        
        Args:
            page: Page number (1-based)
            per_page: Records per page (max 200)
            
        Returns:
            List of subscription records
        """
        endpoint = "/billing/v1/subscriptions"
        params = {
            "organization_id": self.organization_id,
            "page": page,
            "per_page": min(per_page, 200)
        }
        
        try:
            response = await self.client.get(endpoint, params=params)
            subscriptions = response.get("subscriptions", [])
            
            logger.debug(f"  📄 Billing Subscriptions page {page}: {len(subscriptions)} records")
            
            return subscriptions
            
        except ZohoAPIError as e:
            logger.warning(f"  ⚠️ Billing Subscriptions API error on page {page}: {e}")
            return []
        except Exception as e:
            logger.error(f"  ❌ Unexpected error fetching Billing Subscriptions: {e}", exc_info=True)
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

    async def fetch_all_subscriptions(
        self, 
        max_pages: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetches all subscriptions with pagination.
        
        Args:
            max_pages: Maximum pages to fetch (safety limit)
            
        Returns:
            List of all subscription records
        """
        logger.info(f"    🔄 Fetching Books Subscriptions (max {max_pages} pages)...")
        
        all_subscriptions = []
        page = 1
        
        while page <= max_pages:
            subscriptions = await self.get_subscriptions(page=page, per_page=200)
            
            if not subscriptions:
                logger.debug(f"    📄 Page {page}: No more subscriptions")
                break
            
            all_subscriptions.extend(subscriptions)
            logger.info(f"    📄 Page {page}: Fetched {len(subscriptions)} subscriptions (Total: {len(all_subscriptions)})")
            
            # If we got less than 200, we're on the last page
            if len(subscriptions) < 200:
                logger.info(f"    ✅ Last page reached ({len(subscriptions)} < 200)")
                break
            
            page += 1
            
            # Rate limiting
            import asyncio
            await asyncio.sleep(0.6)
        
        logger.info(f"    ✅ Total Books Subscriptions fetched: {len(all_subscriptions)}")
        
        return all_subscriptions

    def close(self):
        """
        Close is handled by the parent ZohoClient.
        This is a no-op for Books client.
        """
        pass

