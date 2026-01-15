"""
CRM Provider Factory.
Implements factory pattern for loading CRM integrations dynamically.
"""

import logging
from functools import lru_cache
from typing import Optional

from app.core.config import get_settings
from app.core.interfaces.crm import CRMProvider

logger = logging.getLogger(__name__)


class CRMProviderError(Exception):
    """Raised when CRM provider cannot be loaded or initialized."""
    pass


@lru_cache
def get_crm_provider() -> Optional[CRMProvider]:
    """
    Factory function to get the configured CRM provider.
    
    Reads ACTIVE_CRM_PROVIDER from settings and dynamically loads
    the corresponding provider implementation.
    
    Returns:
        Configured CRM provider instance, or None if no provider is active
        
    Raises:
        CRMProviderError: If provider is configured but cannot be loaded
        
    Example:
        >>> provider = get_crm_provider()
        >>> if provider:
        ...     if provider.check_connection():
        ...         data = provider.fetch_skeleton_data(["Contacts"])
    """
    settings = get_settings()
    
    active_provider = settings.active_crm_provider.lower() if settings.active_crm_provider else None
    
    if not active_provider or active_provider == "none":
        logger.info("ℹ️ No CRM provider configured")
        return None
    
    logger.info(f"🔌 Loading CRM provider: {active_provider}")
    
    # Factory pattern: Load provider based on configuration
    try:
        if active_provider == "zoho":
            return _load_zoho_provider()

        elif active_provider == "twenty":
            return _load_twenty_provider()

        else:
            raise CRMProviderError(
                f"Unknown CRM provider: {active_provider}. "
                f"Supported providers: zoho, twenty"
            )
            
    except Exception as e:
        logger.error(f"❌ Failed to load CRM provider '{active_provider}': {e}")
        raise CRMProviderError(f"Failed to load CRM provider: {e}") from e


def _load_zoho_provider() -> CRMProvider:
    """
    Loads and initializes Zoho CRM provider.
    
    Returns:
        Configured ZohoCRMProvider instance
        
    Raises:
        CRMProviderError: If Zoho credentials are missing or invalid
    """
    settings = get_settings()
    
    # Validate required credentials
    if not settings.zoho_client_id:
        raise CRMProviderError("ZOHO_CLIENT_ID not configured")
    
    if not settings.zoho_client_secret:
        raise CRMProviderError("ZOHO_CLIENT_SECRET not configured")
    
    if not settings.zoho_refresh_token:
        raise CRMProviderError("ZOHO_REFRESH_TOKEN not configured")
    
    # Import here to avoid loading integration code if not needed
    from app.integrations.zoho import ZohoCRMProvider
    
    logger.info("✅ Initializing Zoho CRM provider")
    
    # Optional: Zoho Books integration
    books_org_id = getattr(settings, 'zoho_books_organization_id', None)
    if books_org_id:
        logger.info(f"✅ Zoho Books integration enabled (org_id: {books_org_id})")
    
    # Optional: Zoho Analytics integration
    analytics_workspace_id = getattr(settings, 'zoho_analytics_workspace_id', None)
    analytics_org_id = getattr(settings, 'zoho_analytics_org_id', None)
    analytics_api_url = getattr(settings, 'zoho_analytics_api_base_url', 'https://analyticsapi.zoho.eu')
    if analytics_workspace_id and analytics_org_id:
        logger.info(f"✅ Zoho Analytics integration enabled (workspace_id: {analytics_workspace_id}, org_id: {analytics_org_id})")
    elif analytics_workspace_id and not analytics_org_id:
        logger.warning("⚠️ ZOHO_ANALYTICS_WORKSPACE_ID set but ZOHO_ANALYTICS_ORG_ID missing!")

    provider = ZohoCRMProvider(
        client_id=settings.zoho_client_id,
        client_secret=settings.zoho_client_secret,
        refresh_token=settings.zoho_refresh_token,
        api_base_url=settings.zoho_api_base_url,
        books_organization_id=books_org_id,
        analytics_workspace_id=analytics_workspace_id,
        analytics_org_id=analytics_org_id,
        analytics_api_base_url=analytics_api_url,
    )
    
    # Verify connection
    try:
        if not provider.check_connection():
            logger.warning("⚠️ Zoho CRM connection check failed")
            # Don't raise error, allow app to start
            # Connection issues might be temporary
    except Exception as e:
        logger.warning(f"⚠️ Zoho CRM connection check error: {e}")
    
    return provider


def _load_twenty_provider() -> CRMProvider:
    """
    Loads and initializes Twenty CRM provider.

    Returns:
        Configured TwentyCRMProvider instance

    Raises:
        CRMProviderError: If Twenty credentials are missing or invalid
    """
    settings = get_settings()

    # Validate required credentials
    if not settings.twenty_api_url:
        raise CRMProviderError("TWENTY_API_URL not configured")

    if not settings.twenty_api_token:
        raise CRMProviderError("TWENTY_API_TOKEN not configured")

    # Import here to avoid loading integration code if not needed
    from app.integrations.twenty import TwentyCRMProvider

    logger.info("✅ Initializing Twenty CRM provider")

    provider = TwentyCRMProvider(
        api_url=settings.twenty_api_url,
        api_token=settings.twenty_api_token,
    )

    # Verify connection
    try:
        if not provider.check_connection():
            logger.warning("⚠️ Twenty CRM connection check failed")
    except Exception as e:
        logger.warning(f"⚠️ Twenty CRM connection check error: {e}")

    return provider


def clear_crm_provider_cache() -> None:
    """
    Clears the cached CRM provider instance.
    
    Useful for testing or when credentials are updated at runtime.
    """
    logger.info("🔄 Clearing CRM provider cache")
    get_crm_provider.cache_clear()


def is_crm_available() -> bool:
    """
    Quick check if a CRM provider is configured and available.
    
    Returns:
        True if a CRM provider is active, False otherwise
    """
    try:
        provider = get_crm_provider()
        return provider is not None
    except Exception as e:
        logger.error(f"❌ CRM availability check failed: {e}")
        return False

