"""
Zoho Analytics API Client for SQL Queries.
Provides access to Zoho Analytics data warehouse for Books-CRM mapping.

Uses the Bulk Export API (async) since synchronous SQL query endpoint requires
workspace ID (not name) and the /sqlquery endpoint doesn't exist in API v2.
"""

import asyncio
import json
import logging
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class ZohoAnalyticsError(Exception):
    """Raised when Zoho Analytics API returns an error."""
    pass


class ZohoAnalyticsClient:
    """
    Zoho Analytics API Client for executing SQL queries.

    Uses Zoho Analytics Bulk Export API v2 to execute SQL queries
    against the data warehouse. This is an async API that requires:
    1. Create export job
    2. Poll for job completion
    3. Download results
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        workspace_id: str,
        org_id: str,
        api_base_url: str = "https://analyticsapi.zoho.eu",
        auth_url: str = "https://accounts.zoho.eu/oauth/v2/token",
    ):
        """
        Initialize Zoho Analytics client.

        Args:
            client_id: Zoho OAuth client ID
            client_secret: Zoho OAuth client secret
            refresh_token: Long-lived refresh token
            workspace_id: Zoho Analytics workspace ID (numeric, e.g., "170896000000004002")
            org_id: Zoho Analytics Organization ID (required for ZANALYTICS-ORGID header)
            api_base_url: Zoho Analytics API base URL (region-specific)
            auth_url: Zoho OAuth token endpoint (region-specific)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.workspace_id = workspace_id
        self.org_id = org_id
        self.api_base_url = api_base_url.rstrip("/")
        self.auth_url = auth_url

        # Token cache
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

        # HTTP client with longer timeout for bulk operations
        self._client = httpx.AsyncClient(timeout=120.0)

        logger.info(f"ZohoAnalyticsClient initialized (workspace_id: {workspace_id}, org_id: {org_id})")

    def _get_headers(self, token: str) -> Dict[str, str]:
        """Get standard headers for Analytics API requests."""
        return {
            "Authorization": f"Zoho-oauthtoken {token}",
            "ZANALYTICS-ORGID": self.org_id,
        }

    async def _get_access_token(self) -> str:
        """
        Gets valid access token, refreshing if necessary.

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

    async def _create_export_job(self, sql: str, response_format: str = "json") -> str:
        """
        Creates a bulk export job for SQL query.

        Args:
            sql: SQL query string
            response_format: Output format (json, csv, xml)

        Returns:
            Job ID

        Raises:
            ZohoAnalyticsError: If job creation fails
        """
        token = await self._get_access_token()

        config = {
            "sqlQuery": sql,
            "responseFormat": response_format
        }
        config_encoded = urllib.parse.quote(json.dumps(config))

        url = f"{self.api_base_url}/restapi/v2/bulk/workspaces/{self.workspace_id}/data?CONFIG={config_encoded}"

        try:
            response = await self._client.get(url, headers=self._get_headers(token))

            if response.status_code >= 400:
                error_msg = f"Failed to create export job: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise ZohoAnalyticsError(error_msg)

            result = response.json()

            if result.get("status") != "success":
                raise ZohoAnalyticsError(f"Export job creation failed: {result}")

            job_id = result.get("data", {}).get("jobId")
            if not job_id:
                raise ZohoAnalyticsError(f"No jobId in response: {result}")

            logger.debug(f"      Export job created: {job_id}")
            return job_id

        except httpx.RequestError as e:
            raise ZohoAnalyticsError(f"Network error creating export job: {e}")

    async def _wait_for_job(self, job_id: str, max_attempts: int = 30, poll_interval: float = 1.0) -> bool:
        """
        Polls for job completion.

        Args:
            job_id: Export job ID
            max_attempts: Maximum polling attempts
            poll_interval: Seconds between polls

        Returns:
            True if job completed successfully

        Raises:
            ZohoAnalyticsError: If job fails or times out
        """
        token = await self._get_access_token()
        url = f"{self.api_base_url}/restapi/v2/bulk/workspaces/{self.workspace_id}/exportjobs/{job_id}"

        for attempt in range(max_attempts):
            try:
                response = await self._client.get(url, headers=self._get_headers(token))

                if response.status_code >= 400:
                    raise ZohoAnalyticsError(f"Failed to check job status: {response.status_code}")

                result = response.json()
                job_status = result.get("data", {}).get("jobStatus", "")

                if "COMPLETED" in job_status:
                    logger.debug(f"      Export job {job_id} completed")
                    return True
                elif "FAILED" in job_status:
                    raise ZohoAnalyticsError(f"Export job failed: {result}")

                # Job still in progress
                await asyncio.sleep(poll_interval)

            except httpx.RequestError as e:
                raise ZohoAnalyticsError(f"Network error checking job status: {e}")

        raise ZohoAnalyticsError(f"Job {job_id} timed out after {max_attempts} attempts")

    async def _download_job_data(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Downloads data from completed export job.

        Args:
            job_id: Export job ID

        Returns:
            List of row dictionaries
        """
        token = await self._get_access_token()
        url = f"{self.api_base_url}/restapi/v2/bulk/workspaces/{self.workspace_id}/exportjobs/{job_id}/data"

        try:
            response = await self._client.get(url, headers=self._get_headers(token))

            if response.status_code >= 400:
                raise ZohoAnalyticsError(f"Failed to download job data: {response.status_code}")

            # Response is JSON array directly
            data = response.json()

            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # Handle wrapped response
                return data.get("data", data.get("rows", []))
            else:
                logger.warning(f"Unexpected response format: {type(data)}")
                return []

        except httpx.RequestError as e:
            raise ZohoAnalyticsError(f"Network error downloading job data: {e}")

    async def execute_sql(
        self,
        sql: str,
        output_format: str = "json"
    ) -> List[Dict[str, Any]]:
        """
        Executes a SQL query against Zoho Analytics workspace.

        Uses the Bulk Export API (async):
        1. Creates export job
        2. Polls for completion
        3. Downloads results

        Args:
            sql: SQL query string
            output_format: Output format (json, csv, xml)

        Returns:
            List of row dictionaries

        Raises:
            ZohoAnalyticsError: If query fails
        """
        logger.debug(f"      Executing SQL via Bulk API: {sql[:100]}...")

        # Step 1: Create export job
        job_id = await self._create_export_job(sql, output_format)

        # Step 2: Wait for job completion
        await self._wait_for_job(job_id)

        # Step 3: Download results
        rows = await self._download_job_data(job_id)

        logger.debug(f"      SQL query returned {len(rows)} rows")
        return rows

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

