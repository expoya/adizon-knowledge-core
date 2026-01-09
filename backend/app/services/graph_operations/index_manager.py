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
        1. GLOBAL source_id index - Critical for ALL relationship lookups!
        2. CRMEntity.source_id - Specific CRM relations
        3. User.source_id - For HAS_OWNER relations
        4. Document.source_document_id - For document graph
        
        NOTE: The global source_id index is CRITICAL! Without it, relationship
        creation does full node scans (58k nodes × 1000 rels = 58M operations per chunk!)
        """
        logger.info("🔧 Creating database indexes...")
        
        try:
            with self.driver.session(database="neo4j") as session:
                # Index 0: GLOBAL source_id index (MOST CRITICAL!)
                # This allows MATCH (n {source_id: ...}) to use an index
                # Without label restriction, enabling fast lookups across all node types
                self._create_global_text_index(
                    session,
                    "global_source_id",
                    "source_id"
                )
                
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
                
                # Index 3: Document.source_document_id
                self._create_index(
                    session,
                    "doc_source_id",
                    "Document",
                    "source_document_id"
                )
                    
        except Exception as e:
            logger.error(f"❌ CRITICAL: Failed to create indexes: {e}", exc_info=True)
            # Don't raise - let app continue but log the error
    
    def _create_global_text_index(
        self,
        session: Any,
        index_name: str,
        property_name: str
    ) -> None:
        """
        Create a global TEXT index that works across all labels.
        
        This enables MATCH (n {property: value}) to use an index
        even without specifying a label.
        
        Neo4j 5.x syntax: CREATE TEXT INDEX name FOR (n) ON (n.property)
        
        Args:
            session: Neo4j session
            index_name: Name of the index
            property_name: Property to index
        """
        try:
            # Neo4j 5.x: TEXT index for cross-label property lookups
            result = session.run(
                f"CREATE TEXT INDEX {index_name} IF NOT EXISTS FOR (n) ON (n.{property_name})"
            )
            result.consume()  # Force execution
            logger.info(f"✅ Global TEXT index created: {property_name} (works across all labels)")
        except Exception as e:
            # If TEXT index fails (older Neo4j), try RANGE index
            logger.warning(f"⚠️ TEXT index failed, trying RANGE index: {e}")
            try:
                result = session.run(
                    f"CREATE INDEX {index_name} IF NOT EXISTS FOR (n) ON (n.{property_name})"
                )
                result.consume()
                logger.info(f"✅ Global RANGE index created: {property_name}")
            except Exception as e2:
                logger.error(f"❌ Failed to create global index {index_name}: {e2}")
    
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
    

