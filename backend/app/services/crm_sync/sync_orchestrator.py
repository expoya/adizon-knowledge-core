"""
CRM Sync Orchestrator.

Coordinates the CRM synchronization workflow.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from app.core.interfaces.crm import CRMProvider
from app.services.graph_store import GraphStoreService
from app.services.crm_sync.property_sanitizer import PropertySanitizer
from app.services.crm_sync.error_tracker import ErrorTracker
from app.services.crm_sync.node_batch_processor import NodeBatchProcessor
from app.services.crm_sync.relationship_processor import RelationshipProcessor

logger = logging.getLogger(__name__)


@dataclass
class CRMSyncResult:
    """Result of CRM sync operation."""
    status: str
    entities_synced: int
    entities_created: int
    entities_updated: int
    relationships_created: int
    entity_types: List[str]
    message: str
    errors: List[str]
    
    @property
    def is_success(self) -> bool:
        """Check if sync was fully successful."""
        return self.status == "success" and len(self.errors) == 0
    
    @property
    def is_partial_success(self) -> bool:
        """Check if sync had partial success."""
        return self.status in ["success", "partial_success"] and len(self.errors) > 0


class CRMSyncOrchestrator:
    """
    Orchestrates CRM sync workflow.
    
    Responsibilities:
    - Coordinate sync phases
    - Manage dependencies between processors
    - Aggregate results & errors
    - Handle incremental sync timestamps
    """
    
    def __init__(self, graph_store: GraphStoreService):
        """
        Initialize CRM sync orchestrator.
        
        Args:
            graph_store: Graph store service for Neo4j operations
        """
        self.graph_store = graph_store
        self.property_sanitizer = PropertySanitizer()
        self.error_tracker = ErrorTracker()
        self.node_processor = NodeBatchProcessor(graph_store)
        self.relationship_processor = RelationshipProcessor(graph_store)
    
    async def sync(
        self,
        provider: CRMProvider,
        entity_types: Optional[List[str]] = None
    ) -> CRMSyncResult:
        """
        Execute CRM synchronization.
        
        Workflow:
        1. Get last sync timestamp (incremental sync)
        2. Fetch skeleton data from CRM
        3. Sanitize properties
        4. Create/update nodes in batches
        5. Create relationships in batches
        6. Update sync timestamp
        7. Return results with error tracking
        
        Args:
            provider: CRM provider instance
            entity_types: Optional list of entity types to sync
            
        Returns:
            CRMSyncResult with statistics and errors
        """
        provider_name = provider.get_provider_name()
        logger.info(f"🔄 CRM Sync: Starting synchronization with {provider_name}")
        logger.debug(f"Entity types requested: {entity_types or 'default'}")
        
        # Start status tracking
        from app.services.sync_status import sync_status, SyncPhase
        sync_status.start_sync()
        
        # Clear previous errors
        self.error_tracker.clear()
        
        try:
            # === PHASE 1: Fetch Data ===
            logger.debug("Phase 1: Fetching data from CRM...")
            sync_status.update_phase(SyncPhase.FETCHING, "Fetching data from CRM...")
            
            # FORCE FULL SYNC: Incremental sync temporarily disabled
            # Reason: Modified_Time filter causes INVALID_QUERY errors in Zoho COQL
            last_sync_time = None
            logger.info(f"📥 FULL SYNC: Incremental sync disabled (Modified_Time filter issues)")
            
            logger.debug(f"Calling provider.fetch_skeleton_data()...")
            
            skeleton_data = await provider.fetch_skeleton_data(
                entity_types=entity_types,
                last_sync_time=last_sync_time
            )
            
            if not skeleton_data:
                return CRMSyncResult(
                    status="success",
                    entities_synced=0,
                    entities_created=0,
                    entities_updated=0,
                    relationships_created=0,
                    entity_types=entity_types or [],
                    message="No entities found in CRM",
                    errors=[]
                )
            
            logger.info(f"✅ Fetched {len(skeleton_data)} entities from CRM")
            
            # === PHASE 2: Prepare Data ===
            logger.debug("Phase 2: Preparing data (sanitizing properties, grouping)...")
            sync_status.update_phase(SyncPhase.PREPARING, "Preparing data (sanitizing & grouping)...")
            entities_by_label, all_relations = self._prepare_data(skeleton_data)
            sync_status.update_fetching("All entities", len(skeleton_data))
            
            logger.info(
                f"📊 Grouped into {len(entities_by_label)} labels "
                f"with {len(all_relations)} relations"
            )
            logger.debug(f"Labels: {list(entities_by_label.keys())}")
            
            # === PHASE 3: Process Nodes ===
            logger.debug("Phase 3: Processing nodes...")
            sync_status.update_phase(SyncPhase.PROCESSING_NODES, "Creating/updating nodes in graph...")
            node_result = await self.node_processor.process_nodes(
                entities_by_label, provider_name
            )
            logger.debug(f"Node processing complete: {node_result.created} created, {node_result.updated} updated")
            
            # === PHASE 4: Process Relationships ===
            logger.debug("Phase 4: Processing relationships...")
            sync_status.update_phase(SyncPhase.PROCESSING_RELATIONSHIPS, f"Creating {len(all_relations)} relationships...")
            rel_result = await self.relationship_processor.process_relationships(
                all_relations
            )
            logger.debug(f"Relationship processing complete: {rel_result.created} created")
            
            # === PHASE 5: Update Sync Timestamp ===
            logger.debug("Phase 5: Updating sync timestamp...")
            sync_status.update_phase(SyncPhase.UPDATING_METADATA, "Updating sync metadata...")
            await self._update_sync_timestamp()
            logger.debug("Sync timestamp updated")
            
            # === PHASE 6: Build Result ===
            result = self._build_result(
                node_result,
                rel_result,
                provider_name
            )
            
            # Mark as completed
            sync_status.complete_sync(success=True)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ CRM sync failed: {e}", exc_info=True)
            self.error_tracker.track_batch_error("sync_workflow", 0, e)
            
            # Mark as failed
            from app.services.sync_status import sync_status
            sync_status.add_error(str(e))
            sync_status.complete_sync(success=False)
            
            return CRMSyncResult(
                status="error",
                entities_synced=0,
                entities_created=0,
                entities_updated=0,
                relationships_created=0,
                entity_types=entity_types or [],
                message=f"CRM sync failed: {str(e)}",
                errors=[str(e)]
            )
    
    def _prepare_data(self, skeleton_data: List[dict]) -> tuple:
        """
        Prepare data for processing.
        
        Sanitizes properties and groups entities by label.
        
        Args:
            skeleton_data: Raw skeleton data from provider
            
        Returns:
            Tuple of (entities_by_label, all_relations)
        """
        entities_by_label = {}
        all_relations = []
        
        for entity in skeleton_data:
            try:
                label = entity.get("label")
                if not label:
                    logger.warning(f"⚠️ Skipping entity without label: {entity}")
                    continue
                
                # Group by label
                if label not in entities_by_label:
                    entities_by_label[label] = []
                
                # Sanitize properties
                raw_props = entity.get("properties", {})
                sanitized_props = self.property_sanitizer.sanitize(raw_props)
                
                entities_by_label[label].append({
                    "source_id": entity["source_id"],
                    "properties": sanitized_props
                })
                
                # Collect relations
                for rel in entity.get("relations", []):
                    all_relations.append({
                        "source_id": entity["source_id"],
                        "target_id": rel["target_id"],
                        "edge_type": rel["edge_type"],
                        "target_label": rel.get("target_label", "CRMEntity"),
                        "direction": rel["direction"]
                    })
                    
            except Exception as e:
                entity_id = entity.get("source_id", "unknown")
                self.error_tracker.track_entity_error(
                    entity_id,
                    entity.get("label", "unknown"),
                    e,
                    context={"properties": entity.get("properties")}
                )
                continue
        
        return entities_by_label, all_relations
    
    async def _get_last_sync_time(self) -> Optional[datetime]:
        """Get last sync timestamp for incremental sync."""
        try:
            return await self.graph_store.get_last_sync_time("crm_sync")
        except Exception as e:
            logger.warning(f"⚠️ Failed to get last sync time: {e}")
            return None
    
    async def _update_sync_timestamp(self):
        """Update last sync timestamp."""
        try:
            # Use None to let sync_metadata generate properly formatted timestamp
            # Format will be: YYYY-MM-DDTHH:MM:SS.sss+00:00 (with milliseconds)
            await self.graph_store.set_last_sync_time(None, "crm_sync")
            logger.info(f"🔄 Updated last sync time")
        except Exception as e:
            logger.warning(f"⚠️ Failed to update last sync time: {e}")
            # Don't fail the sync if timestamp update fails
    
    def _build_result(
        self,
        node_result,
        rel_result,
        provider_name: str
    ) -> CRMSyncResult:
        """
        Build final sync result.
        
        Args:
            node_result: Result from node processor
            rel_result: Result from relationship processor
            provider_name: CRM provider name
            
        Returns:
            CRMSyncResult
        """
        total_synced = node_result.created + node_result.updated
        total_failed = node_result.failed + rel_result.failed
        
        # Get error messages
        error_summary = self.error_tracker.get_summary()
        error_messages = error_summary.get_error_messages(limit=15)
        
        # Determine status
        if total_failed > 0 or error_messages:
            status = "partial_success"
            message = (
                f"Partial sync completed: {total_synced} entities synced "
                f"({node_result.created} created, {node_result.updated} updated), "
                f"{total_failed} failed, "
                f"{rel_result.created} relationships created"
            )
        else:
            status = "success"
            message = (
                f"CRM Sync completed successfully: {total_synced} entities synced "
                f"({node_result.created} created, {node_result.updated} updated), "
                f"{rel_result.created} relationships created"
            )
        
        logger.info(f"✅ {message}")
        
        return CRMSyncResult(
            status=status,
            entities_synced=total_synced,
            entities_created=node_result.created,
            entities_updated=node_result.updated,
            relationships_created=rel_result.created,
            entity_types=node_result.labels_processed,
            message=message,
            errors=error_messages
        )

