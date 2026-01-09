"""
Graph Store Service for Neo4j knowledge graph.

Facade for modular graph operations.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from neo4j import GraphDatabase

from app.core.config import get_settings
from app.services.graph_operations import (
    GraphIndexManager,
    GraphNodeOperations,
    GraphQueryService,
    GraphRelationshipOperations,
    GraphSyncMetadata,
)

settings = get_settings()
logger = logging.getLogger(__name__)


class GraphStoreService:
    """
    Facade for Neo4j graph operations.
    
    Delegates to specialized services:
    - index_manager: Index management
    - node_ops: Node CRUD operations
    - rel_ops: Relationship CRUD operations
    - query_service: Query and search operations
    - sync_metadata: Sync timestamp management
    """

    def __init__(self):
        """Initialize Neo4j driver and sub-services."""
        logger.info("🔧 Initializing GraphStoreService...")
        
        try:
            logger.debug(f"Connecting to Neo4j at {settings.neo4j_uri}")
            self.driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
            
            # Verify connectivity
            logger.debug("Verifying Neo4j connectivity...")
            self.driver.verify_connectivity()
            logger.info("✅ Neo4j connection verified")
            
            # Initialize sub-services
            logger.debug("Initializing sub-services...")
            self.index_manager = GraphIndexManager(self.driver)
            logger.debug("  ✓ GraphIndexManager initialized")
            
            self.node_ops = GraphNodeOperations(self.driver)
            logger.debug("  ✓ GraphNodeOperations initialized")
            
            self.rel_ops = GraphRelationshipOperations(self.driver)
            logger.debug("  ✓ GraphRelationshipOperations initialized")
            
            self.query_service = GraphQueryService(self.driver)
            logger.debug("  ✓ GraphQueryService initialized")
            
            self.sync_metadata = GraphSyncMetadata(self.driver)
            logger.debug("  ✓ GraphSyncMetadata initialized")
            
            # Create indexes for performance
            logger.info("Creating performance indexes...")
            self.index_manager.ensure_indexes()
            logger.info("✅ GraphStoreService fully initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize GraphStoreService: {e}", exc_info=True)
            raise

    def close(self):
        """Close the Neo4j driver."""
        self.driver.close()
    
    # ===== Node Operations (delegate to node_ops) =====

    async def add_entity(
        self,
        label: str,
        name: str,
        properties: Optional[Dict] = None,
        document_id: Optional[str] = None,
    ) -> str:
        """Add an entity (node) to the graph. Delegates to node_ops."""
        return await self.node_ops.add_entity(label, name, properties, document_id)
    
    # ===== Relationship Operations (delegate to rel_ops) =====
    
    async def add_relationship(
        self,
        from_entity: Tuple[str, str],
        to_entity: Tuple[str, str],
        relationship_type: str,
        properties: Optional[Dict] = None,
    ) -> None:
        """Add a relationship between two entities. Delegates to rel_ops."""
        await self.rel_ops.add_relationship(from_entity, to_entity, relationship_type, properties)

    async def add_graph_documents(
        self,
        entities: List[dict],
        relationships: List[dict],
        document_id: str,
        source_file: Optional[str] = None,
    ) -> dict:
        """
        Add extracted graph data to Neo4j with PENDING status for review.
        
        High-level method that coordinates node and relationship creation.
        """
        # Create nodes
        nodes_result = await self.node_ops.add_graph_documents(entities, document_id, source_file)
        
        # Create relationships
        rels_result = await self.rel_ops.add_graph_relationships(relationships, document_id, source_file)
        
        return {
            "nodes_created": nodes_result["nodes_created"],
            "relationships_created": rels_result["relationships_created"],
        }
    
    # ===== Query Operations (delegate to query_service) =====

    async def query(self, cypher: str, parameters: Optional[dict] = None) -> List[dict]:
        """Execute a custom Cypher query. Delegates to query_service."""
        return await self.query_service.query(cypher, parameters)

    async def query_graph(self, question: str) -> str:
        """Query the knowledge graph for information. Delegates to query_service."""
        return await self.query_service.query_graph(question)

    async def get_graph_summary(self) -> str:
        """Get a summary of the knowledge graph. Delegates to query_service."""
        return await self.query_service.get_summary()
    
    # ===== Delete Operations (delegate to node_ops) =====

    async def delete_by_filename(self, filename: str) -> int:
        """Delete all nodes associated with a filename. Delegates to node_ops."""
        return await self.node_ops.delete_by_filename(filename)

    async def delete_by_document_id(self, document_id: str) -> int:
        """Delete all nodes associated with a document ID. Delegates to node_ops."""
        return await self.node_ops.delete_by_document_id(document_id)
    
    # ===== Sync Metadata Operations (delegate to sync_metadata) =====

    async def get_last_sync_time(self, sync_key: str = "crm_sync") -> Optional[str]:
        """Get the last sync timestamp. Delegates to sync_metadata."""
        return await self.sync_metadata.get_last_sync_time(sync_key)

    async def set_last_sync_time(self, timestamp: Optional[str] = None, sync_key: str = "crm_sync") -> None:
        """Set the last sync timestamp. Delegates to sync_metadata."""
        await self.sync_metadata.set_last_sync_time(timestamp, sync_key)


# Singleton instance
_graph_store_service: GraphStoreService | None = None


def get_graph_store_service() -> GraphStoreService:
    """Get or create graph store service singleton."""
    global _graph_store_service
    if _graph_store_service is None:
        _graph_store_service = GraphStoreService()
    return _graph_store_service

