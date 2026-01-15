"""
Twenty CRM API Client.
Handles authentication and HTTP requests to Twenty REST API.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class TwentyAPIError(Exception):
    """Raised when Twenty API returns an error."""
    pass


class TwentyClient:
    """
    Twenty CRM REST API Client.

    Uses Bearer token authentication for API access.
    Supports cursor-based pagination.
    """

    def __init__(
        self,
        api_url: str,
        api_token: str,
        timeout: float = 30.0,
    ):
        """
        Initialize Twenty client.

        Args:
            api_url: Twenty API base URL (e.g., https://api.twenty.com)
            api_token: Twenty API token
            timeout: HTTP request timeout in seconds
        """
        self.api_url = api_url.rstrip("/")
        self.api_token = api_token

        # HTTP client
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
        )

        logger.info(f"TwentyClient initialized (url: {self.api_url})")

    async def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Makes an authenticated request to Twenty API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/rest/people")
            params: Query parameters
            json: JSON body for POST/PUT

        Returns:
            API response as dictionary

        Raises:
            TwentyAPIError: If API returns an error
        """
        url = f"{self.api_url}{endpoint}"

        try:
            response = await self._client.request(
                method=method,
                url=url,
                params=params,
                json=json,
            )

            # Handle errors
            if response.status_code >= 400:
                error_msg = f"Twenty API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise TwentyAPIError(error_msg)

            # Parse JSON response
            if not response.text or response.text.strip() == "":
                return {}

            return response.json()

        except httpx.RequestError as e:
            raise TwentyAPIError(f"Network error: {e}")

    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """GET request shorthand."""
        return await self.request("GET", endpoint, params=params)

    async def post(
        self,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """POST request shorthand."""
        return await self.request("POST", endpoint, params=params, json=json)

    async def fetch_all(
        self,
        endpoint: str,
        data_key: str,
        limit: int = 50,
        max_pages: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Fetches all records from an endpoint with cursor-based pagination.

        Args:
            endpoint: API endpoint (e.g., "/rest/people")
            data_key: Key in response.data containing the records (e.g., "people")
            limit: Records per page
            max_pages: Maximum pages to fetch (0 = unlimited)

        Returns:
            List of all records
        """
        all_data = []
        cursor = None
        page = 1

        while True:
            params = {"limit": limit}
            if cursor:
                params["starting_after"] = cursor

            logger.debug(f"Fetching {endpoint} page {page}...")
            response = await self.get(endpoint, params=params)

            # Extract data
            data = response.get("data", {}).get(data_key, [])
            if not data:
                break

            all_data.extend(data)
            logger.info(f"  Page {page}: Fetched {len(data)} records (Total: {len(all_data)})")

            # Check pagination
            page_info = response.get("pageInfo", {})
            if not page_info.get("hasNextPage", False):
                break

            cursor = page_info.get("endCursor")
            if not cursor:
                break

            # Check max pages limit
            if max_pages > 0 and page >= max_pages:
                logger.info(f"  Stopping after {max_pages} pages (max_pages limit)")
                break

            page += 1

        logger.info(f"Total {data_key} fetched: {len(all_data)} records")
        return all_data

    async def close(self):
        """Closes the HTTP client."""
        await self._client.aclose()
        logger.info("TwentyClient closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
