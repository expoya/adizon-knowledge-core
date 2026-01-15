"""
Data Fetching Logic for Twenty CRM.

Handles REST API fetching with cursor-based pagination.
"""

import logging
from typing import Any, Dict, List

from app.integrations.twenty.client import TwentyClient
from app.integrations.twenty.schema import get_endpoint, get_data_key

logger = logging.getLogger(__name__)


async def fetch_entity_type(
    client: TwentyClient,
    entity_type: str,
    limit: int = 50,
    max_pages: int = 0,
) -> List[Dict[str, Any]]:
    """
    Fetches all records for an entity type.

    Args:
        client: TwentyClient instance
        entity_type: Entity type name (e.g., "people", "companies")
        limit: Records per page
        max_pages: Maximum pages to fetch (0 = unlimited)

    Returns:
        List of raw records from Twenty API
    """
    endpoint = get_endpoint(entity_type)
    data_key = get_data_key(entity_type)

    logger.info(f"  Fetching {entity_type} from {endpoint}...")

    records = await client.fetch_all(
        endpoint=endpoint,
        data_key=data_key,
        limit=limit,
        max_pages=max_pages,
    )

    logger.info(f"  Fetched {len(records)} {entity_type}")
    return records


async def fetch_single_entity(
    client: TwentyClient,
    entity_type: str,
    entity_id: str,
) -> Dict[str, Any]:
    """
    Fetches a single entity by ID.

    Args:
        client: TwentyClient instance
        entity_type: Entity type name (e.g., "people", "companies")
        entity_id: Entity UUID

    Returns:
        Single entity record

    Raises:
        TwentyAPIError: If entity not found or API error
    """
    endpoint = get_endpoint(entity_type)
    data_key = get_data_key(entity_type)

    # Twenty uses singular endpoint for single record
    # e.g., /rest/people/{id} returns {"data": {"person": {...}}}
    singular_key = data_key.rstrip("s") if data_key.endswith("ies") else data_key[:-1]
    if data_key == "companies":
        singular_key = "company"
    elif data_key == "opportunities":
        singular_key = "opportunity"
    elif data_key == "people":
        singular_key = "person"

    response = await client.get(f"{endpoint}/{entity_id}")
    return response.get("data", {}).get(singular_key, {})


async def fetch_related_entities(
    client: TwentyClient,
    entity_type: str,
    related_type: str,
    entity_id: str,
) -> List[Dict[str, Any]]:
    """
    Fetches entities related to a specific entity.

    For example, fetch all opportunities for a company:
    - entity_type: "companies"
    - related_type: "opportunities"
    - entity_id: company UUID

    Args:
        client: TwentyClient instance
        entity_type: Parent entity type
        related_type: Related entity type to fetch
        entity_id: Parent entity UUID

    Returns:
        List of related entity records
    """
    related_endpoint = get_endpoint(related_type)
    related_data_key = get_data_key(related_type)

    # Build filter based on relationship
    filter_field = None
    if entity_type == "companies":
        filter_field = "companyId"
    elif entity_type == "people":
        filter_field = "personId"  # For tasks/notes via targets

    if not filter_field:
        logger.warning(f"No filter field for {entity_type} -> {related_type}")
        return []

    # Twenty uses filter query params
    # e.g., /rest/opportunities?filter[companyId][eq]=uuid
    params = {
        f"filter[{filter_field}][eq]": entity_id,
        "limit": 50,
    }

    response = await client.get(related_endpoint, params=params)
    return response.get("data", {}).get(related_data_key, [])
