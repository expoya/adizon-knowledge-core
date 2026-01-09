"""
DEBUG: Check if ZOHO_BOOKS_ORGANIZATION_ID is loaded correctly.
"""

import os
import sys
sys.path.insert(0, 'backend')

from app.core.config import get_settings

settings = get_settings()

print("=" * 60)
print("DEBUG: ZOHO_BOOKS_ORGANIZATION_ID")
print("=" * 60)

# Check ENV directly
env_value = os.getenv("ZOHO_BOOKS_ORGANIZATION_ID")
print(f"\n1. ENV Variable (direct):")
print(f"   ZOHO_BOOKS_ORGANIZATION_ID = {env_value!r}")
print(f"   Type: {type(env_value)}")

# Check Pydantic Settings
pydantic_value = settings.zoho_books_organization_id
print(f"\n2. Pydantic Settings (settings.zoho_books_organization_id):")
print(f"   Value = {pydantic_value!r}")
print(f"   Type: {type(pydantic_value)}")

# Check via getattr (wie in crm_factory.py)
getattr_value = getattr(settings, 'zoho_books_organization_id', None)
print(f"\n3. Via getattr (wie in crm_factory.py):")
print(f"   Value = {getattr_value!r}")
print(f"   Type: {type(getattr_value)}")

# All settings
print(f"\n4. All Zoho Settings:")
print(f"   zoho_client_id = {settings.zoho_client_id[:20] if settings.zoho_client_id else None}...")
print(f"   zoho_client_secret = {settings.zoho_client_secret[:20] if settings.zoho_client_secret else None}...")
print(f"   zoho_refresh_token = {settings.zoho_refresh_token[:20] if settings.zoho_refresh_token else None}...")
print(f"   zoho_api_base_url = {settings.zoho_api_base_url}")
print(f"   zoho_books_organization_id = {settings.zoho_books_organization_id}")

print("\n" + "=" * 60)

# Check if value is truthy
if getattr_value:
    print("✅ books_organization_id IS SET - Books should be enabled!")
else:
    print("❌ books_organization_id IS NOT SET - Books will be disabled!")
    
print("=" * 60)

