"""
Zoho API Client with OAuth2 Refresh Token Flow.
Handles authentication, token refresh, and HTTP requests.
"""

import logging
import time
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class ZohoAuthError(Exception):
    """Raised when Zoho authentication fails."""
    pass


class ZohoAPIError(Exception):
    """Raised when Zoho API returns an error."""
    pass


class ZohoClient:
    """
    Zoho CRM API Client with automatic token refresh.
    
    Implements OAuth2 Refresh Token flow for persistent authentication.
    Handles rate limiting and error responses.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        api_base_url: str = "https://www.zohoapis.eu",
        auth_url: str = "https://accounts.zoho.eu/oauth/v2/token",
    ):
        """
        Initialize Zoho client.
        
        Args:
            client_id: Zoho OAuth client ID
            client_secret: Zoho OAuth client secret
            refresh_token: Long-lived refresh token
            api_base_url: Zoho API base URL (region-specific)
            auth_url: Zoho OAuth token endpoint (region-specific)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.api_base_url = api_base_url.rstrip("/")
        self.auth_url = auth_url
        
        # Token cache
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        
        # HTTP client
        self._client = httpx.AsyncClient(timeout=30.0)
        
        logger.info("ZohoClient initialized")

    async def _refresh_access_token(self) -> str:
        """
        Refreshes the access token using the refresh token.
        
        Returns:
            New access token
            
        Raises:
            ZohoAuthError: If token refresh fails
        """
        logger.info("🔄 Refreshing Zoho access token...")
        
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
                raise ZohoAuthError(f"Token refresh failed: {response.status_code} - {response.text}")
            
            data = response.json()
            
            if "access_token" not in data:
                raise ZohoAuthError(f"No access_token in response: {data}")
            
            # Cache token (Zoho tokens typically valid for 1 hour)
            self._access_token = data["access_token"]
            expires_in = data.get("expires_in_sec", 3600)
            self._token_expires_at = time.time() + expires_in - 60  # 60s safety buffer
            
            logger.info(f"✅ Access token refreshed (valid for {expires_in}s)")
            
            return self._access_token
            
        except httpx.RequestError as e:
            raise ZohoAuthError(f"Network error during token refresh: {e}")

    async def _get_access_token(self) -> str:
        """
        Gets valid access token, refreshing if necessary.
        
        Returns:
            Valid access token
        """
        # Check if we have a valid cached token
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token
        
        # Refresh token
        return await self._refresh_access_token()

    async def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Makes an authenticated request to Zoho API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/crm/v6/Contacts")
            params: Query parameters
            json: JSON body for POST/PUT
            
        Returns:
            API response as dictionary
            
        Raises:
            ZohoAPIError: If API returns an error
        """
        # Get valid token
        token = await self._get_access_token()
        
        # Build full URL
        url = f"{self.api_base_url}{endpoint}"
        
        # Make request
        try:
            response = await self._client.request(
                method=method,
                url=url,
                params=params,
                json=json,
                headers={
                    "Authorization": f"Zoho-oauthtoken {token}",
                }
            )
            
            # Handle errors
            if response.status_code >= 400:
                error_msg = f"Zoho API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise ZohoAPIError(error_msg)
            
            return response.json()
            
        except httpx.RequestError as e:
            raise ZohoAPIError(f"Network error: {e}")

    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET request shorthand."""
        return await self.request("GET", endpoint, params=params)

    async def post(
        self,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """POST request shorthand."""
        return await self.request("POST", endpoint, params=params, json=json)

    async def close(self):
        """Closes the HTTP client."""
        await self._client.aclose()
        logger.info("ZohoClient closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

