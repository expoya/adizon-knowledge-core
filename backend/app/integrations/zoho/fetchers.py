"""
Data Fetching Logic for Zoho CRM.

Handles both COQL and REST API fetching with pagination and error recovery.
"""

import asyncio
import logging
from typing import Any, Dict, List

from app.integrations.zoho.client import ZohoAPIError, ZohoClient

logger = logging.getLogger(__name__)


async def fetch_via_coql(
    client: ZohoClient,
    module_name: str,
    fields: List[str],
    where_clause: str = "id is not null",
    limit: int = 50,
    max_pages: int = 1
) -> List[Dict[str, Any]]:
    """
    Fetches records via Zoho COQL with pagination.
    
    Args:
        client: ZohoClient instance
        module_name: Zoho module name (e.g., "Accounts", "Leads")
        fields: List of fields to retrieve
        where_clause: SQL WHERE clause
        limit: Records per page (max 10000 for COQL)
        max_pages: Maximum pages to fetch (for testing)
        
    Returns:
        List of records
    """
    logger.info(f"    🔄 Fetching via COQL: {module_name}")
    logger.info(f"    🔥 SMOKE TEST MODE: LIMIT {limit}, max {max_pages} page(s)")
    
    all_data = []
    offset = 0
    page = 1
    
    while True:
        try:
            # Build paginated query
            query = f"SELECT {', '.join(fields)} FROM {module_name} WHERE {where_clause} LIMIT {limit} OFFSET {offset}"
            logger.debug(f"    Query (Page {page}): {query}")
            
            # Execute query via COQL endpoint
            response = await client.post(
                "/crm/v6/coql",
                json={"select_query": query}
            )
            
            data = response.get("data", [])
            
            if not data:
                logger.debug(f"    📄 Page {page}: No more records")
                break  # No more records
            
            all_data.extend(data)
            logger.info(f"    📄 Page {page}: Fetched {len(data)} records (Total: {len(all_data)})")
            
            # 🔥 SMOKE TEST: Stop after max_pages
            if page >= max_pages:
                logger.info(f"    🔥 SMOKE TEST: Stopping after {max_pages} page(s)")
                break
            
            # Check if we got less than limit (last page)
            if len(data) < limit:
                logger.info(f"    ✅ Last page reached ({len(data)} < {limit})")
                break
            
            # Increment for next page
            offset += limit
            page += 1
            
            # Rate Limit Protection: Sleep 0.6s between calls
            # Zoho allows 100 calls/min = 1 call every 0.6s
            await asyncio.sleep(0.6)
            
        except ZohoAPIError as e:
            error_msg = str(e).lower()
            # Check for Finance module errors
            if module_name in ["Zoho_Books", "Subscriptions__s", "Einw_nde"] and ("not_supported" in error_msg or "400" in str(e)):
                logger.warning(f"    ⚠️ COQL not supported for {module_name}")
                break
            else:
                logger.error(f"    ❌ API error on page {page}: {e}")
                # Continue with what we have (error recovery)
                break
        
        except Exception as e:
            logger.error(f"    ❌ Unexpected error on page {page}: {e}", exc_info=True)
            # Continue with what we have (error recovery)
            break
    
    return all_data


async def fetch_via_rest_api(
    client: ZohoClient,
    module_name: str,
    fields: List[str],
    limit: int = 50,
    max_pages: int = 1
) -> List[Dict[str, Any]]:
    """
    Fetches records via Zoho REST API with pagination.
    
    Used for modules that don't support COQL (Invoices, Subscriptions, Emails).
    
    Args:
        client: ZohoClient instance
        module_name: Zoho module name (e.g., "Invoices", "Emails")
        fields: List of fields to retrieve
        limit: Records per page (max 200 for REST API)
        max_pages: Maximum pages to fetch (for testing)
        
    Returns:
        List of records
    """
    logger.info(f"    🔄 Fetching via REST API: {module_name}")
    
    all_data = []
    page_num = 1
    rest_limit = min(limit, 200)  # REST API max 200 per page
    
    while page_num <= max_pages:  # 🔥 SMOKE TEST: Limited pages
        try:
            # Build REST API endpoint
            # NOTE: Emails module uses v2 API, not v6!
            api_version = "v2" if module_name == "Emails" else "v6"
            endpoint = f"/crm/{api_version}/{module_name}"
            
            # Build query parameters
            params = {
                "fields": ",".join(fields),
                "per_page": rest_limit,
                "page": page_num
            }
            
            # Execute request
            response = await client.get(endpoint, params=params)
            
            # Return data field
            data_page = response.get("data", [])
            
            if not data_page:
                if page_num == 1:
                    logger.warning(f"    ⚠️ {module_name}: No records found (empty module)")
                else:
                    logger.debug(f"    📄 Page {page_num}: No more records")
                break
            
            all_data.extend(data_page)
            logger.info(f"    📄 Page {page_num}: Fetched {len(data_page)} records (Total: {len(all_data)})")
            
            # 🔥 SMOKE TEST: Stop after max_pages
            if page_num >= max_pages:
                logger.info(f"    🔥 SMOKE TEST: Stopping after {max_pages} page(s)")
                break
            
            # Check if we got less than limit (last page)
            if len(data_page) < rest_limit:
                logger.info(f"    ✅ Last page reached ({len(data_page)} < {rest_limit})")
                break
            
            # Increment page
            page_num += 1
            
            # Rate Limit Protection
            await asyncio.sleep(0.6)
            
        except ZohoAPIError as e:
            logger.error(f"    ❌ REST API failed for {module_name} (page {page_num}) | Error: {str(e)}")
            break
            
        except Exception as e:
            logger.error(f"    ❌ REST API error for {module_name} (page {page_num}): {e}", exc_info=True)
            break
    
    return all_data


async def fetch_users_via_api(client: ZohoClient) -> List[Dict[str, Any]]:
    """
    Fetches users via special Users API endpoint.
    
    Users have a dedicated API endpoint and don't support COQL.
    
    Args:
        client: ZohoClient instance
        
    Returns:
        List of user records
    """
    logger.info("    🔄 Fetching Users via special API endpoint")
    
    try:
        response = await client.get("/crm/v6/users", params={"type": "ActiveUsers"})
        users = response.get("users", [])
        
        logger.info(f"    ✅ Fetched {len(users)} Users")
        return users
        
    except Exception as e:
        logger.warning(f"    ⚠️ Users API error: {e}")
        return []

