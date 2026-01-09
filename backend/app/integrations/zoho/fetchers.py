"""
Data Fetching Logic for Zoho CRM.

Handles both COQL and REST API fetching with pagination and error recovery.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List

from app.integrations.zoho.client import ZohoAPIError, ZohoClient

logger = logging.getLogger(__name__)


def _filter_notes(notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter out unwanted Notes:
    1. note_title = "Terminbuchung" or "Kontaktversuch"
    2. Created before 2024-04-01
    
    Args:
        notes: List of Note records
        
    Returns:
        Filtered list of Notes
    """
    cutoff_date = datetime(2024, 4, 1)
    filtered = []
    
    for note in notes:
        # Filter by title
        note_title = note.get("Note_Title", "")
        if note_title in ["Terminbuchung", "Kontaktversuch"]:
            continue
        
        # Filter by date (Created_Time format: "2024-01-15T10:30:00+01:00")
        created_time_str = note.get("Created_Time")
        if created_time_str:
            try:
                # Parse ISO format
                created_time = datetime.fromisoformat(created_time_str.replace("Z", "+00:00"))
                if created_time < cutoff_date:
                    continue
            except (ValueError, AttributeError):
                # If parsing fails, keep the note (better safe than sorry)
                logger.debug(f"Could not parse Created_Time for note {note.get('id')}: {created_time_str}")
        
        filtered.append(note)
    
    return filtered


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
            
            # Log first query at INFO level for debugging
            if page == 1:
                logger.info(f"    🔍 COQL Query: {query[:200]}...")
            
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
            # Check for Finance module errors (COQL not supported)
            if module_name in ["Zoho_Books", "Subscriptions__s"] and ("not_supported" in error_msg or "coql" in error_msg):
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
    Fetches records via Zoho REST API with page_token pagination.
    
    Zoho REST API Pagination:
    - First 2000 records: Use 'page' parameter (pages 1-10 @ 200 per page)
    - Beyond 2000: Must use 'page_token' from response
    - Response contains: info.more_records + info.next_page_token
    
    Special Filtering:
    - Notes: Filters out "Terminbuchung", "Kontaktversuch", and notes before 2024-04-01
    
    Args:
        client: ZohoClient instance
        module_name: Zoho module name (e.g., "Deals", "Tasks", "Notes")
        fields: List of fields to retrieve
        limit: Records per page (max 200 for REST API)
        max_pages: Maximum pages to fetch (0 = unlimited)
        
    Returns:
        List of records (filtered if module_name == "Notes")
    """
    logger.info(f"    🔄 Fetching via REST API: {module_name}")
    
    all_data = []
    page_num = 1
    rest_limit = min(limit, 200)  # REST API max 200 per page
    page_token = None
    filtered_count = 0  # Track how many Notes were filtered out
    
    while True:
        try:
            # Build REST API endpoint
            # NOTE: Emails module uses v2 API, not v6!
            api_version = "v2" if module_name == "Emails" else "v6"
            endpoint = f"/crm/{api_version}/{module_name}"
            
            # Build query parameters
            params = {
                "fields": ",".join(fields),
                "per_page": rest_limit
            }
            
            # Use page_token if we have one (for records beyond 2000)
            # Otherwise use page number (for first 2000 records)
            if page_token:
                params["page_token"] = page_token
                logger.debug(f"    📄 Using page_token pagination (beyond record 2000)")
            else:
                params["page"] = page_num
            
            # Execute request
            response = await client.get(endpoint, params=params)
            
            # Extract data and pagination info
            data_page = response.get("data", [])
            info = response.get("info", {})
            more_records = info.get("more_records", False)
            next_page_token = info.get("next_page_token")
            
            if not data_page:
                if page_num == 1:
                    logger.warning(f"    ⚠️ {module_name}: No records found (empty module)")
                else:
                    logger.debug(f"    📄 Page {page_num}: No more records")
                break
            
            # Apply Notes filtering if needed
            if module_name == "Notes":
                filtered_page = _filter_notes(data_page)
                filtered_count += len(data_page) - len(filtered_page)
                all_data.extend(filtered_page)
                logger.info(
                    f"    📄 Page {page_num}: Fetched {len(data_page)} records, "
                    f"kept {len(filtered_page)} after filtering (Total: {len(all_data)})"
                )
            else:
                all_data.extend(data_page)
                logger.info(f"    📄 Page {page_num}: Fetched {len(data_page)} records (Total: {len(all_data)})")
            
            # Check if max_pages limit reached (0 = unlimited)
            if max_pages > 0 and page_num >= max_pages:
                logger.info(f"    ⏸️ Stopping after {max_pages} page(s) (max_pages limit)")
                break
            
            # Check if there are more records
            if not more_records:
                logger.info(f"    ✅ All records fetched (more_records=false)")
                break
            
            # Update page_token for next iteration
            if next_page_token:
                page_token = next_page_token
            
            # Increment page counter
            page_num += 1
            
            # Rate Limit Protection (100 calls/minute = 0.6s per call)
            await asyncio.sleep(0.6)
            
        except ZohoAPIError as e:
            # If DISCRETE_PAGINATION_LIMIT_EXCEEDED and we have data, continue with page_token
            if "DISCRETE_PAGINATION_LIMIT_EXCEEDED" in str(e) and all_data:
                logger.warning(f"    ⚠️ Hit 2000 record limit on page {page_num}, need page_token to continue")
                logger.info(f"    ℹ️ Fetched {len(all_data)} records so far, but more exist")
                break
            else:
                logger.error(f"    ❌ REST API failed for {module_name} (page {page_num}) | Error: {str(e)}")
                break
            
        except Exception as e:
            logger.error(f"    ❌ REST API error for {module_name} (page {page_num}): {e}", exc_info=True)
            break
    
    # Log summary
    if module_name == "Notes" and filtered_count > 0:
        logger.info(
            f"    ✅ Total {module_name} fetched: {len(all_data)} records "
            f"({filtered_count} filtered out)"
        )
    else:
        logger.info(f"    ✅ Total {module_name} fetched: {len(all_data)} records")
    
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

