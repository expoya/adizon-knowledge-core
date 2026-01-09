"""
Graph Index Manager.

Manages Neo4j indexes for performance optimization.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class GraphIndexManager:
    """
    Manages Neo4j indexes for performance.
    
    CRITICAL: Without indexes, relation creation takes HOURS for large datasets!
    With indexes: Milliseconds per relation.
    """
    
    def __init__(self, driver: Any):
        """
        Initialize index manager.
        
        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver
    
    def ensure_indexes(self) -> None:
        """
        Create indexes for performance-critical properties.
        
        Indexes:
        1. CRMEntity.source_id - Critical for CRM relations
        2. User.source_id - For HAS_OWNER relations
        3. source_document_id - For document graph
        """
        logger.info("🔧 Creating database indexes...")
        
        try:
            with self.driver.session(database="neo4j") as session:
                # Index 1: CRMEntity.source_id (CRITICAL!)
                self._create_index(
                    session,
                    "crm_source_id",
                    "CRMEntity",
                    "source_id"
                )
                
                # Index 2: User.source_id
                self._create_index(
                    session,
                    "user_source_id",
                    "User",
                    "source_id"
                )
                
                # Index 3: source_document_id (for all nodes)
                self._create_index_on_all_nodes(
                    session,
                    "doc_source_id",
                    "source_document_id"
                )
                    
        except Exception as e:
            logger.error(f"❌ CRITICAL: Failed to create indexes: {e}", exc_info=True)
            # Don't raise - let app continue but log the error
    
    def _create_index(
        self,
        session: Any,
        index_name: str,
        label: str,
        property_name: str
    ) -> None:
        """
        Create a single index for a label and property.
        
        Args:
            session: Neo4j session
            index_name: Name of the index
            label: Node label
            property_name: Property to index
        """
        try:
            result = session.run(
                f"CREATE INDEX {index_name} IF NOT EXISTS FOR (n:{label}) ON (n.{property_name})"
            )
            result.consume()  # Force execution
            logger.info(f"✅ Index created: {label}.{property_name}")
        except Exception as e:
            logger.error(f"❌ Failed to create index {index_name}: {e}")
    
    def _create_index_on_all_nodes(
        self,
        session: Any,
        index_name: str,
        property_name: str
    ) -> None:
        """
        Create an index on a property for all nodes (no label).
        
        Args:
            session: Neo4j session
            index_name: Name of the index
            property_name: Property to index
        """
        try:
            result = session.run(
                f"CREATE INDEX {index_name} IF NOT EXISTS FOR (n) ON (n.{property_name})"
            )
            result.consume()  # Force execution
            logger.info(f"✅ Index created: {property_name} (all labels)")
        except Exception as e:
            logger.error(f"❌ Failed to create index {index_name}: {e}")

