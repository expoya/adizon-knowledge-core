"""
Graph Node Operations.

CRUD operations for Neo4j nodes.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import partial
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Thread pool for running blocking operations
_executor = ThreadPoolExecutor(max_workers=2)


class GraphNodeOperations:
    """
    Handles node CRUD operations in Neo4j.
    
    Features:
    - Create/Merge nodes
    - Update nodes
    - Delete nodes (single, by document_id, by filename)
    - Query nodes
    """
    
    def __init__(self, driver: Any):
        """
        Initialize node operations.
        
        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver
    
    async def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous function in the thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, partial(func, *args, **kwargs)
        )
    
    async def add_entity(
        self,
        label: str,
        name: str,
        properties: Optional[Dict] = None,
        document_id: Optional[str] = None,
    ) -> str:
        """
        Add an entity (node) to the graph.
        
        Args:
            label: Node label (e.g., 'Person', 'Organization')
            name: Entity name (used as unique identifier)
            properties: Additional properties for the node
            document_id: Source document ID for provenance
            
        Returns:
            Node ID
        """
        props = properties or {}
        props["name"] = name
        if document_id:
            props["source_document_id"] = document_id

        return await self._run_sync(
            self.driver.execute_query,
            f"""
            MERGE (n:{label} {{name: $name}})
            SET n += $properties
            SET n.updated_at = datetime()
            RETURN elementId(n) as node_id
            """,
            name=name,
            properties=props,
            database_="neo4j",
        )
    
    async def add_graph_documents(
        self,
        entities: List[dict],
        document_id: str,
        source_file: Optional[str] = None,
    ) -> dict:
        """
        Add extracted graph entities to Neo4j with PENDING status for review.

        Args:
            entities: List of dicts with 'label', 'name', and optional 'properties'
            document_id: Source document ID
            source_file: Optional source filename for provenance

        Returns:
            Summary of created nodes
        """
        nodes_created = 0
        created_at = datetime.now(timezone.utc).isoformat()

        # Create entities with PENDING status
        for entity in entities:
            props = entity.get("properties", {})
            props["source_document_id"] = document_id
            props["status"] = "PENDING"  # Review-Status
            props["created_at"] = created_at
            if source_file:
                props["source_file"] = source_file

            await self._run_sync(
                self.driver.execute_query,
                f"""
                MERGE (n:{entity['label']} {{name: $name}})
                SET n += $properties
                SET n.updated_at = datetime()
                """,
                name=entity["name"],
                properties=props,
                database_="neo4j",
            )
            nodes_created += 1

        return {"nodes_created": nodes_created}
    
    async def delete_by_filename(self, filename: str) -> int:
        """
        Delete all nodes associated with a specific filename.

        Args:
            filename: The source filename to delete

        Returns:
            Number of deleted nodes
        """
        logger.info(f"Deleting graph nodes for filename: {filename}")

        try:
            # First count how many we'll delete
            count_result = await self._run_sync(
                self.driver.execute_query,
                """
                MATCH (n)
                WHERE n.source_file CONTAINS $filename
                RETURN count(n) as count
                """,
                filename=filename,
                database_="neo4j",
            )

            delete_count = count_result.records[0]["count"] if count_result.records else 0

            # Then delete nodes (DETACH DELETE also removes relationships)
            await self._run_sync(
                self.driver.execute_query,
                """
                MATCH (n)
                WHERE n.source_file CONTAINS $filename
                DETACH DELETE n
                """,
                filename=filename,
                database_="neo4j",
            )

            logger.info(f"Deleted {delete_count} graph nodes for filename: {filename}")
            return delete_count

        except Exception as e:
            logger.error(f"Failed to delete graph nodes for {filename}: {e}")
            raise
    
    async def delete_by_document_id(self, document_id: str) -> int:
        """
        Delete all nodes associated with a specific document ID.

        Args:
            document_id: The source document ID to delete

        Returns:
            Number of deleted nodes
        """
        logger.info(f"Deleting graph nodes for document_id: {document_id}")

        try:
            # First count how many we'll delete
            count_result = await self._run_sync(
                self.driver.execute_query,
                """
                MATCH (n)
                WHERE n.source_document_id = $document_id
                RETURN count(n) as count
                """,
                document_id=document_id,
                database_="neo4j",
            )

            delete_count = count_result.records[0]["count"] if count_result.records else 0

            # Then delete nodes (DETACH DELETE also removes relationships)
            await self._run_sync(
                self.driver.execute_query,
                """
                MATCH (n)
                WHERE n.source_document_id = $document_id
                DETACH DELETE n
                """,
                document_id=document_id,
                database_="neo4j",
            )

            logger.info(f"Deleted {delete_count} graph nodes for document_id: {document_id}")
            return delete_count

        except Exception as e:
            logger.error(f"Failed to delete graph nodes for document {document_id}: {e}")
            raise

