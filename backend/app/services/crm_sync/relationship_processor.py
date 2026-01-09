"""
Relationship Processor for CRM Sync.

Handles batch creation of Neo4j relationships with proper typing.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.services.graph_store import GraphStoreService

logger = logging.getLogger(__name__)


@dataclass
class RelationshipProcessingResult:
    """Result of relationship processing."""
    created: int
    skipped: int  # Skipped because target node doesn't exist
    failed: int
    relationship_types: List[str]


class RelationshipProcessor:
    """
    Processes relationship creation in batches.
    
    Features:
    - Relationship grouping by (edge_type, target_label, direction)
    - Dynamic Cypher generation
    - MATCH-based creation (no orphan nodes)
    - Proper handling of INCOMING/OUTGOING directions
    """
    
    def __init__(self, graph_store: GraphStoreService):
        """
        Initialize relationship processor.
        
        Args:
            graph_store: Graph store service for Neo4j operations
        """
        self.graph_store = graph_store
    
    async def process_relationships(
        self,
        relations: List[Dict]
    ) -> RelationshipProcessingResult:
        """
        Process all relationships.
        
        Args:
            relations: List of relation dicts with:
                      - source_id: Source node ID
                      - target_id: Target node ID
                      - edge_type: Relationship type (e.g., "HAS_OWNER")
                      - target_label: Target node label (e.g., "User", "CRMEntity")
                      - direction: "OUTGOING" or "INCOMING"
            
        Returns:
            RelationshipProcessingResult with statistics
        """
        # Group by (edge_type, target_label, direction)
        relations_by_key = self._group_relations(relations)
        
        total_created = 0
        total_skipped = 0
        total_failed = 0
        relationship_types = []
        
        logger.info(
            f"🔗 Processing {len(relations)} relationships "
            f"across {len(relations_by_key)} relation types"
        )
        logger.debug(f"Relation types: {[(e, t, d) for e, t, d in relations_by_key.keys()]}")
        
        for (edge_type, target_label, direction), batch_relations in relations_by_key.items():
            try:
                logger.info(
                    f"  🔄 Processing {edge_type} → {target_label} ({direction}) "
                    f"with {len(batch_relations)} relations..."
                )
                result = await self._process_relationship_batch(
                    edge_type, target_label, direction, batch_relations
                )
                
                total_created += result["count"]
                relationship_types.append(f"{edge_type} → {target_label}")
                
                logger.info(
                    f"  ✅ {edge_type} → {target_label} ({direction}): "
                    f"{result['count']} relationships"
                )
                
                # Update status tracker
                from app.services.sync_status import sync_status
                sync_status.update_relationship_processing(edge_type, result['count'])
                
            except Exception as e:
                logger.error(
                    f"  ❌ Failed to create {edge_type} → {target_label} relationships: {e}",
                    exc_info=True
                )
                total_failed += len(batch_relations)
                continue
        
        return RelationshipProcessingResult(
            created=total_created,
            skipped=total_skipped,
            failed=total_failed,
            relationship_types=relationship_types
        )
    
    def _group_relations(
        self,
        relations: List[Dict]
    ) -> Dict[Tuple[str, str, str], List[Dict]]:
        """
        Group relations by (edge_type, target_label, direction).
        
        This allows batch processing of similar relationships.
        
        Args:
            relations: List of relation dicts
            
        Returns:
            Dict mapping (edge_type, target_label, direction) -> list of relations
        """
        relations_by_key = {}
        
        for rel in relations:
            key = (
                rel["edge_type"],
                rel.get("target_label", "CRMEntity"),
                rel["direction"]
            )
            if key not in relations_by_key:
                relations_by_key[key] = []
            relations_by_key[key].append(rel)
        
        return relations_by_key
    
    async def _process_relationship_batch(
        self,
        edge_type: str,
        target_label: str,
        direction: str,
        relations: List[Dict]
    ) -> Dict:
        """
        Process single relationship batch with chunking.
        
        Uses MATCH (not MERGE) for target nodes to avoid creating orphans.
        Relationships are only created if both source AND target exist.
        
        CRITICAL: Neo4j cannot handle 100k+ relationships in one UNWIND!
        We split into chunks of 1000 relationships per query.
        
        Args:
            edge_type: Relationship type (e.g., "HAS_OWNER")
            target_label: Target node label (e.g., "User")
            direction: "OUTGOING" or "INCOMING"
            relations: List of relations
            
        Returns:
            Dict with count of relationships created
        """
        # Sanitize edge type and label
        safe_edge = ''.join(c for c in edge_type if c.isalnum() or c == '_')
        safe_target_label = ''.join(c for c in target_label if c.isalnum() or c == '_')
        
        # Build Cypher query based on direction
        cypher_query = self._build_cypher_query(
            safe_edge, safe_target_label, direction
        )
        
        # Split into chunks of 1000 to avoid memory/timeout issues
        chunk_size = 1000
        total_count = 0
        
        for i in range(0, len(relations), chunk_size):
            chunk = relations[i:i + chunk_size]
            chunk_num = (i // chunk_size) + 1
            total_chunks = (len(relations) + chunk_size - 1) // chunk_size
            
            # Always log for relationships (critical for debugging)
            logger.info(
                f"    🔄 {edge_type} chunk {chunk_num}/{total_chunks} "
                f"({len(chunk)} relationships)..."
            )
            
            result = await self.graph_store.query(
                cypher_query,
                parameters={"batch": chunk}
            )
            
            if result and len(result) > 0:
                chunk_count = result[0].get("count", 0)
                total_count += chunk_count
                logger.info(f"      ✅ Chunk {chunk_num}: {chunk_count} relationships created")
            
            # Small delay between chunks to give Neo4j time for GC
            # Skip for last chunk
            if chunk_num < total_chunks:
                await asyncio.sleep(0.1)
        
        return {"count": total_count}
    
    def _build_cypher_query(
        self,
        edge_type: str,
        target_label: str,
        direction: str
    ) -> str:
        """
        Generate Cypher query for relationship batch.
        
        Args:
            edge_type: Sanitized edge type
            target_label: Sanitized target label
            direction: "OUTGOING" or "INCOMING"
            
        Returns:
            Cypher query string
        """
        if direction == "OUTGOING":
            # (source)-[edge]->(target)
            # NOTE: Using MATCH (not MERGE) for target to avoid orphan nodes
            # CRITICAL: Use CRMEntity label for source to leverage index!
            # All CRM nodes (including Users) have CRMEntity label
            return f"""
            UNWIND $batch as row
            MATCH (a:CRMEntity {{source_id: row.source_id}})
            MATCH (b:{target_label} {{source_id: row.target_id}})
            MERGE (a)-[r:{edge_type}]->(b)
            ON CREATE SET r.created_at = datetime()
            RETURN count(r) as count
            """
        
        elif direction == "INCOMING":
            # (target)-[edge]->(source)
            # NOTE: Using MATCH (not MERGE) for target to avoid orphan nodes
            # CRITICAL: Use CRMEntity label for source to leverage index!
            return f"""
            UNWIND $batch as row
            MATCH (a:CRMEntity {{source_id: row.source_id}})
            MATCH (b:{target_label} {{source_id: row.target_id}})
            MERGE (b)-[r:{edge_type}]->(a)
            ON CREATE SET r.created_at = datetime()
            RETURN count(r) as count
            """
        
        else:
            raise ValueError(f"Invalid direction: {direction}. Must be 'OUTGOING' or 'INCOMING'")

