"""
Node Batch Processor for CRM Sync.

Handles batch creation of Neo4j nodes with error recovery.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List

from app.services.graph_store import GraphStoreService

logger = logging.getLogger(__name__)


@dataclass
class NodeProcessingResult:
    """Result of node processing."""
    created: int
    updated: int
    failed: int
    labels_processed: List[str]


class NodeBatchProcessor:
    """
    Processes node creation in batches.
    
    Features:
    - Batch UNWIND queries for performance
    - Label sanitization (alphanumeric only)
    - Multi-label support (CRMEntity)
    - Automatic created/updated tracking
    """
    
    def __init__(self, graph_store: GraphStoreService):
        """
        Initialize node batch processor.
        
        Args:
            graph_store: Graph store service for Neo4j operations
        """
        self.graph_store = graph_store
    
    async def process_nodes(
        self,
        entities_by_label: Dict[str, List[Dict]],
        provider_name: str
    ) -> NodeProcessingResult:
        """
        Process all nodes grouped by label.
        
        Args:
            entities_by_label: Dict mapping label -> list of entities
                              Each entity has {source_id: str, properties: dict}
            provider_name: CRM provider name (e.g., "zoho")
            
        Returns:
            NodeProcessingResult with statistics
        """
        total_created = 0
        total_updated = 0
        total_failed = 0
        labels_processed = []
        
        logger.info(f"📊 Processing {len(entities_by_label)} node labels")
        logger.debug(f"Labels to process: {list(entities_by_label.keys())}")
        
        for label, entities in entities_by_label.items():
            try:
                logger.debug(f"Processing {label} batch with {len(entities)} entities...")
                result = await self._process_label_batch(label, entities, provider_name)
                total_created += result["created"]
                total_updated += result["updated"]
                labels_processed.append(label)
                
                logger.info(
                    f"  ✅ {label}: {result['count']} nodes "
                    f"({result['created']} created, {result['updated']} updated)"
                )
                
                # Update status tracker
                from app.services.sync_status import sync_status
                sync_status.update_node_processing(label, result['created'], result['updated'])
                
            except Exception as e:
                logger.error(f"  ❌ Failed to process {label} batch: {e}", exc_info=True)
                total_failed += len(entities)
                continue
        
        return NodeProcessingResult(
            created=total_created,
            updated=total_updated,
            failed=total_failed,
            labels_processed=labels_processed
        )
    
    async def _process_label_batch(
        self,
        label: str,
        entities: List[Dict],
        provider_name: str
    ) -> Dict:
        """
        Process single label batch with chunking.
        
        Creates/updates nodes with MERGE query.
        Adds both specific label and CRMEntity label (except for User).
        
        CRITICAL: Neo4j cannot handle 10k+ nodes in one MERGE!
        We split into chunks of 1000 nodes per transaction.
        
        Args:
            label: Node label (e.g., "Lead", "Account")
            entities: List of entities with source_id and properties
            provider_name: CRM provider name
            
        Returns:
            Dict with count, created, updated
        """
        # Sanitize label (alphanumeric only)
        safe_label = ''.join(c for c in label if c.isalnum() or c == '_')
        
        # Add CRMEntity as secondary label for ALL CRM nodes
        # This enables efficient relationship lookups using MATCH (n:CRMEntity {source_id: ...})
        # Previously we excluded User, but Users ARE CRM entities too!
        labels_string = f"{safe_label}:CRMEntity"
        
        # Build dynamic MERGE query with label(s)
        # Note: Labels can't be parameterized in Cypher, so we use string formatting
        # This is safe because we sanitize the label above
        cypher_query = f"""
        UNWIND $batch as row
        MERGE (n:{labels_string} {{source_id: row.source_id}})
        ON CREATE SET
            n += row.properties,
            n.created_at = datetime(),
            n.synced_at = datetime(),
            n.source = $source
        ON MATCH SET
            n += row.properties,
            n.synced_at = datetime()
        RETURN count(n) as count,
               sum(CASE WHEN n.created_at = n.synced_at THEN 1 ELSE 0 END) as created,
               sum(CASE WHEN n.created_at <> n.synced_at THEN 1 ELSE 0 END) as updated
        """
        
        # Split into chunks of 1000 to avoid memory/timeout issues
        chunk_size = 1000
        total_count = 0
        total_created = 0
        total_updated = 0
        
        for i in range(0, len(entities), chunk_size):
            chunk = entities[i:i + chunk_size]
            chunk_num = (i // chunk_size) + 1
            total_chunks = (len(entities) + chunk_size - 1) // chunk_size
            
            # Only log for multi-chunk batches to reduce noise
            if total_chunks > 1:
                logger.info(
                    f"    🔄 {label} chunk {chunk_num}/{total_chunks} "
                    f"({len(chunk)} nodes)..."
                )
            
            result = await self.graph_store.query(
                cypher_query,
                parameters={
                    "batch": chunk,
                    "source": provider_name
                }
            )
            
            if result and len(result) > 0:
                chunk_count = result[0].get("count", 0)
                chunk_created = result[0].get("created", 0)
                chunk_updated = result[0].get("updated", 0)
                
                total_count += chunk_count
                total_created += chunk_created
                total_updated += chunk_updated
                
                # Only log for multi-chunk batches
                if total_chunks > 1:
                    logger.info(
                        f"      ✅ Chunk {chunk_num}: {chunk_count} nodes "
                        f"({chunk_created} created, {chunk_updated} updated)"
                    )
            
            # Small delay between chunks to give Neo4j time for GC
            # Skip for last chunk
            if chunk_num < total_chunks:
                await asyncio.sleep(0.1)
        
        return {
            "count": total_count,
            "created": total_created,
            "updated": total_updated
        }

