"""
Twenty CRM Provider Implementation.

Clean orchestration layer that delegates to specialized modules.
"""

import logging
from typing import Any, Dict, List, Optional

from app.core.interfaces.crm import CRMProvider
from app.integrations.twenty.client import TwentyClient, TwentyAPIError
from app.integrations.twenty.fetchers import fetch_entity_type, fetch_single_entity
from app.integrations.twenty.processors import process_twenty_record
from app.integrations.twenty.queries import search_live_facts as execute_live_facts_query
from app.integrations.twenty.schema import get_all_entity_types, get_schema_config

logger = logging.getLogger(__name__)


class TwentyCRMProvider(CRMProvider):
    """
    Twenty CRM integration - Clean orchestration layer.

    Delegates to specialized modules:
    - schema.py: Schema configuration
    - fetchers.py: Data fetching (REST API)
    - processors.py: Data processing
    - queries.py: Live facts queries
    """

    def __init__(
        self,
        api_url: str,
        api_token: str,
    ):
        """Initialize Twenty CRM provider."""
        self.client = TwentyClient(
            api_url=api_url,
            api_token=api_token,
        )
        logger.info(f"TwentyCRMProvider initialized (url: {api_url})")

    def check_connection(self) -> bool:
        """
        Verifies Twenty CRM connection.

        Returns True if client is initialized. Actual connection
        verification happens during first API call (lazy validation).
        """
        logger.info("Checking Twenty CRM connection...")

        try:
            if self.client and hasattr(self.client, "api_url"):
                logger.info("Twenty CRM client initialized")
                return True
            else:
                logger.warning("Twenty CRM client not properly initialized")
                return False

        except Exception as e:
            logger.error(f"Twenty connection check failed: {e}")
            return False

    async def execute_raw_query(self, query: str) -> Any:
        """
        Executes a filter query against Twenty CRM.

        Twenty doesn't have a query language like COQL, so this
        executes a filtered search on the specified endpoint.

        Args:
            query: Query in format "endpoint:filter_field=value"
                   e.g., "companies:name=Acme"

        Returns:
            Query results
        """
        logger.debug(f"Executing query: {query}")

        try:
            # Parse query format: "endpoint:filter_field=value"
            if ":" not in query:
                logger.warning(f"Invalid query format: {query}")
                return []

            endpoint, filter_part = query.split(":", 1)

            # Build filter params
            params = {"limit": 50}
            if "=" in filter_part:
                field, value = filter_part.split("=", 1)
                params[f"filter[{field}][eq]"] = value

            response = await self.client.get(f"/rest/{endpoint}", params=params)

            data = response.get("data", {}).get(endpoint, [])
            logger.debug(f"Query returned {len(data)} records")

            return data

        except TwentyAPIError as e:
            logger.warning(f"Query failed: {e}")
            return []

        except Exception as e:
            logger.error(f"Query execution error: {e}")
            return []

    async def fetch_skeleton_data(
        self,
        entity_types: Optional[List[str]] = None,
        last_sync_time: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetches skeleton data from Twenty CRM with structured graph schema.

        Orchestrates fetching and processing for all entity types.

        Args:
            entity_types: List of entity types to fetch, or None for all
            last_sync_time: ISO timestamp for incremental sync (not yet implemented)

        Returns:
            List of processed records ready for graph ingestion
        """
        if entity_types is None:
            entity_types = get_all_entity_types()

        logger.info(f"Fetching skeleton data from Twenty CRM")
        logger.info(f"  Entity types: {entity_types}")

        results = []

        for entity_type in entity_types:
            try:
                logger.info(f"  Processing {entity_type}...")

                # Fetch raw data
                data = await fetch_entity_type(
                    self.client,
                    entity_type,
                    limit=50,
                    max_pages=0,  # Fetch all
                )

                if not data:
                    logger.warning(f"    No records found for {entity_type}")
                    continue

                # Process records
                for record in data:
                    processed = process_twenty_record(record, entity_type)
                    results.append(processed)

                logger.info(f"    Processed {len(data)} {entity_type}")

            except KeyError:
                logger.warning(f"Unknown entity type '{entity_type}'. Skipping.")
                continue

            except Exception as e:
                logger.error(f"Error processing {entity_type}: {e}", exc_info=True)
                continue

        logger.info(f"Total skeleton data fetched: {len(results)} records")

        return results

    async def search_live_facts(self, entity_id: str, query_context: str) -> str:
        """
        Retrieves live facts about a Twenty entity.

        Delegates to queries module for actual implementation.

        Args:
            entity_id: Twenty record ID (with "twenty_" prefix)
            query_context: Context about what information is needed

        Returns:
            Formatted Markdown string with entity facts
        """
        return await execute_live_facts_query(
            self.client,
            entity_id,
            query_context,
        )

    def get_provider_name(self) -> str:
        """Returns provider name."""
        return "Twenty CRM"

    def get_available_modules(self) -> List[str]:
        """
        Returns available Twenty CRM modules.

        Returns:
            List of module names
        """
        return [
            "companies",
            "people",
            "opportunities",
            "tasks",
            "notes",
        ]

    async def close(self):
        """Closes the underlying HTTP client."""
        await self.client.close()
