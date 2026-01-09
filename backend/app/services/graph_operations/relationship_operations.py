"""
Graph Relationship Operations.

CRUD operations for Neo4j relationships.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import partial
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Thread pool for running blocking operations
_executor = ThreadPoolExecutor(max_workers=2)


class GraphRelationshipOperations:
    """
    Handles relationship CRUD operations in Neo4j.
    
    Features:
    - Create/Merge relationships
    - Query relationships
    - Delete relationships
    """
    
    def __init__(self, driver: Any):
        """
        Initialize relationship operations.
        
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
    
    async def add_relationship(
        self,
        from_entity: Tuple[str, str],  # (label, name)
        to_entity: Tuple[str, str],     # (label, name)
        relationship_type: str,
        properties: Optional[Dict] = None,
    ) -> None:
        """
        Add a relationship between two entities.
        
        Args:
            from_entity: Tuple of (label, name) for source node
            to_entity: Tuple of (label, name) for target node
            relationship_type: Type of relationship (e.g., 'WORKS_FOR')
            properties: Additional properties for the relationship
        """
        from_label, from_name = from_entity
        to_label, to_name = to_entity

        await self._run_sync(
            self.driver.execute_query,
            f"""
            MATCH (a:{from_label} {{name: $from_name}})
            MATCH (b:{to_label} {{name: $to_name}})
            MERGE (a)-[r:{relationship_type}]->(b)
            SET r += $properties
            SET r.updated_at = datetime()
            """,
            from_name=from_name,
            to_name=to_name,
            properties=properties or {},
            database_="neo4j",
        )
    
    async def add_graph_relationships(
        self,
        relationships: List[dict],
        document_id: str,
        source_file: Optional[str] = None,
    ) -> dict:
        """
        Add extracted graph relationships to Neo4j with PENDING status.

        Args:
            relationships: List of dicts with 'from_label', 'from_name',
                          'to_label', 'to_name', 'type', and optional 'properties'
            document_id: Source document ID
            source_file: Optional source filename for provenance

        Returns:
            Summary of created relationships
        """
        rels_created = 0
        created_at = datetime.now(timezone.utc).isoformat()

        # Create relationships with PENDING status
        for rel in relationships:
            rel_props = rel.get("properties", {})
            rel_props["status"] = "PENDING"  # Review-Status
            rel_props["created_at"] = created_at
            rel_props["source_document_id"] = document_id
            if source_file:
                rel_props["source_file"] = source_file

            await self._run_sync(
                self.driver.execute_query,
                f"""
                MATCH (a:{rel['from_label']} {{name: $from_name}})
                MATCH (b:{rel['to_label']} {{name: $to_name}})
                MERGE (a)-[r:{rel['type']}]->(b)
                SET r += $properties
                SET r.updated_at = datetime()
                """,
                from_name=rel["from_name"],
                to_name=rel["to_name"],
                properties=rel_props,
                database_="neo4j",
            )
            rels_created += 1

        return {"relationships_created": rels_created}

