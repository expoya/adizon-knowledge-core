"""
Zoho Analytics API Client for SQL Queries.
Provides access to Zoho Analytics data warehouse for Books-CRM mapping.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class ZohoAnalyticsError(Exception):
    """Raised when Zoho Analytics API returns an error."""
    pass


class ZohoAnalyticsClient:
    """
    Zoho Analytics API Client for executing SQL queries.
    
    Uses Zoho Analytics SQL Query API to access data warehouse views
    that join Books and CRM data.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        workspace_name: str,
        api_base_url: str = "https://analyticsapi.zoho.eu",
        auth_url: str = "https://accounts.zoho.eu/oauth/v2/token",
    ):
        """
        Initialize Zoho Analytics client.
        
        Args:
            client_id: Zoho OAuth client ID
            client_secret: Zoho OAuth client secret
            refresh_token: Long-lived refresh token
            workspace_name: Zoho Analytics workspace name (e.g., "Finance")
            api_base_url: Zoho Analytics API base URL (region-specific)
            auth_url: Zoho OAuth token endpoint (region-specific)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.workspace_name = workspace_name
        self.api_base_url = api_base_url.rstrip("/")
        self.auth_url = auth_url
        
        # Token cache
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        
        # HTTP client
        self._client = httpx.AsyncClient(timeout=60.0)
        
        logger.info(f"ZohoAnalyticsClient initialized (workspace: {workspace_name})")

    async def _get_access_token(self) -> str:
        """
        Gets valid access token, refreshing if necessary.
        Reuses the same OAuth flow as ZohoClient.
        
        Returns:
            Valid access token
        """
        import time
        
        # Check if we have a valid cached token
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token
        
        # Refresh token
        logger.info("🔄 Refreshing Zoho Analytics access token...")
        
        try:
            response = await self._client.post(
                self.auth_url,
                data={
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                }
            )
            
            if response.status_code != 200:
                raise ZohoAnalyticsError(f"Token refresh failed: {response.status_code} - {response.text}")
            
            data = response.json()
            
            if "access_token" not in data:
                raise ZohoAnalyticsError(f"No access_token in response: {data}")
            
            # Cache token
            self._access_token = data["access_token"]
            expires_in = data.get("expires_in_sec", 3600)
            self._token_expires_at = time.time() + expires_in - 60
            
            logger.info(f"✅ Analytics access token refreshed (valid for {expires_in}s)")
            
            return self._access_token
            
        except httpx.RequestError as e:
            raise ZohoAnalyticsError(f"Network error during token refresh: {e}")

    async def execute_sql(
        self, 
        sql: str,
        output_format: str = "json"
    ) -> List[Dict[str, Any]]:
        """
        Executes a SQL query against Zoho Analytics workspace.
        
        Args:
            sql: SQL query string
            output_format: Output format (json, xml, csv)
            
        Returns:
            List of row dictionaries
            
        Raises:
            ZohoAnalyticsError: If query fails
        """
        token = await self._get_access_token()
        
        # Zoho Analytics SQL API v2 endpoint
        # Format: /restapi/v2/workspaces/{workspace}/sqlquery
        url = f"{self.api_base_url}/restapi/v2/workspaces/{self.workspace_name}/sqlquery"
        
        try:
            response = await self._client.post(
                url,
                headers={
                    "Authorization": f"Zoho-oauthtoken {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "sqlQuery": sql,
                    "responseFormat": output_format
                }
            )
            
            if response.status_code >= 400:
                error_msg = f"Zoho Analytics API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise ZohoAnalyticsError(error_msg)
            
            # Parse response
            result = response.json()
            
            # Handle different response formats
            if "data" in result:
                return result["data"].get("rows", [])
            elif "response" in result:
                # Alternative format
                return result["response"].get("result", [])
            else:
                logger.warning(f"Unexpected Analytics API response format: {list(result.keys())}")
                return []
            
        except httpx.RequestError as e:
            raise ZohoAnalyticsError(f"Network error: {e}")

    async def get_customer_crm_mapping(self) -> Dict[str, str]:
        """
        Builds a mapping from Zoho Books customer_id to Zoho CRM account_id.
        
        Uses the "Kunden (Zoho Finance)" table which already joins Books + CRM data.
        
        Returns:
            Dictionary mapping {books_customer_id: crm_account_id}
        """
        logger.info("    🔗 Building Books Customer → CRM Account mapping (via Analytics)...")
        
        sql = """
        SELECT 
            "Kunden-ID" AS books_customer_id,
            "CRM-Referenz-ID" AS crm_account_id
        FROM "Kunden (Zoho Finance)"
        WHERE "CRM-Referenz-ID" IS NOT NULL
        """
        
        try:
            rows = await self.execute_sql(sql)
            
            mapping = {}
            mapped_count = 0
            
            for row in rows:
                books_customer_id = row.get("books_customer_id")
                crm_account_id = row.get("crm_account_id")
                
                if books_customer_id and crm_account_id:
                    mapping[str(books_customer_id)] = str(crm_account_id)
                    mapped_count += 1
            
            logger.info(f"    ✅ Analytics mapping complete: {mapped_count} customers mapped")
            
            return mapping
            
        except ZohoAnalyticsError as e:
            logger.error(f"    ❌ Failed to fetch Analytics mapping: {e}")
            logger.warning("    ⚠️ Falling back to empty mapping")
            return {}

    async def get_invoices_for_account(self, crm_account_id: str) -> List[Dict[str, Any]]:
        """
        Fetches all Books invoices for a given CRM Account.
        
        Args:
            crm_account_id: Zoho CRM Account ID
            
        Returns:
            List of invoice records
        """
        logger.info(f"    📊 Fetching Books Invoices via Analytics for CRM Account: {crm_account_id}")
        
        sql = f"""
        SELECT 
            R."Rechnungsnummer" AS invoice_number,
            R."Rechnungsdatum" AS invoice_date,
            R."Zwischensumme (Basiswährung)" AS total,
            R."Rechnungsstatus" AS status,
            R."Letztes Zahlungsdatum" AS payment_date,
            K."Kundenname" AS customer_name
        FROM "Rechnungen (Zoho Finance)" R
        JOIN "Kunden (Zoho Finance)" K ON K."Kunden-ID" = R."Kunden-ID"
        WHERE K."CRM-Referenz-ID" = '{crm_account_id}'
        ORDER BY R."Rechnungsdatum" DESC
        """
        
        try:
            rows = await self.execute_sql(sql)
            logger.info(f"      ✅ Found {len(rows)} invoices via Analytics")
            return rows
        except ZohoAnalyticsError as e:
            logger.error(f"      ❌ Failed to fetch invoices via Analytics: {e}")
            return []

    async def close(self):
        """Closes the HTTP client."""
        await self._client.aclose()
        logger.info("ZohoAnalyticsClient closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

