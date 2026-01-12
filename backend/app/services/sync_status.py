"""
Real-time Sync Status Tracking.
Allows monitoring of CRM sync progress via API.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class SyncPhase(str, Enum):
    """Sync phases."""
    IDLE = "idle"
    FETCHING = "fetching"
    PREPARING = "preparing"
    PROCESSING_NODES = "processing_nodes"
    PROCESSING_RELATIONSHIPS = "processing_relationships"
    UPDATING_METADATA = "updating_metadata"
    COMPLETED = "completed"
    ERROR = "error"


class SyncStatusTracker:
    """
    Singleton to track sync status across requests.
    Allows real-time monitoring via API.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize status tracking."""
        self.status = {
            "phase": SyncPhase.IDLE,
            "started_at": None,
            "current_step": "Waiting to start...",
            "progress": {
                "entities_fetched": 0,
                "entities_processed": 0,
                "nodes_created": 0,
                "nodes_updated": 0,
                "relationships_created": 0,
                "relationships_failed": 0,
                "current_entity_type": None,
                "current_label": None,
            },
            "errors": [],
            "completed_at": None,
            "duration_seconds": 0
        }
    
    def start_sync(self):
        """Mark sync as started."""
        self.status = {
            "phase": SyncPhase.FETCHING,
            "started_at": datetime.now().isoformat(),
            "current_step": "Starting CRM synchronization...",
            "progress": {
                "entities_fetched": 0,
                "entities_processed": 0,
                "nodes_created": 0,
                "nodes_updated": 0,
                "relationships_created": 0,
                "relationships_failed": 0,
                "current_entity_type": None,
                "current_label": None,
            },
            "errors": [],
            "completed_at": None,
            "duration_seconds": 0
        }
        logger.info("🚀 SYNC STARTED - Status tracking enabled")
    
    def update_phase(self, phase: SyncPhase, step: str):
        """Update current phase."""
        self.status["phase"] = phase
        self.status["current_step"] = step
        logger.info(f"📍 PHASE: {phase.value.upper()} - {step}")
    
    def update_fetching(self, entity_type: str, count: int):
        """Update fetching progress."""
        self.status["progress"]["current_entity_type"] = entity_type
        self.status["progress"]["entities_fetched"] = count
        self.status["current_step"] = f"Fetching {entity_type}... ({count} records)"
        logger.info(f"📥 FETCHING: {entity_type} - {count} records fetched")
    
    def update_node_processing(self, label: str, created: int, updated: int):
        """Update node processing progress."""
        self.status["progress"]["current_label"] = label
        self.status["progress"]["nodes_created"] += created
        self.status["progress"]["nodes_updated"] += updated
        total = self.status["progress"]["nodes_created"] + self.status["progress"]["nodes_updated"]
        self.status["current_step"] = f"Processing {label} nodes... ({created} created, {updated} updated)"
        logger.info(f"📦 NODES: {label} - Created: {created}, Updated: {updated}, Total: {total}")
    
    def update_relationship_processing(self, rel_type: str, count: int):
        """Update relationship processing progress."""
        self.status["progress"]["relationships_created"] += count
        total = self.status["progress"]["relationships_created"]
        self.status["current_step"] = f"Creating {rel_type} relationships... ({count} created)"
        logger.info(f"🔗 RELATIONSHIPS: {rel_type} - Created: {count}, Total so far: {total}")
    
    def add_error(self, error: str):
        """Add error to tracking."""
        self.status["errors"].append({
            "timestamp": datetime.now().isoformat(),
            "error": error
        })
        logger.error(f"❌ ERROR: {error}")
    
    def complete_sync(self, success: bool = True):
        """Mark sync as completed."""
        self.status["phase"] = SyncPhase.COMPLETED if success else SyncPhase.ERROR
        self.status["completed_at"] = datetime.now().isoformat()
        
        # Calculate duration
        if self.status["started_at"]:
            start = datetime.fromisoformat(self.status["started_at"])
            end = datetime.fromisoformat(self.status["completed_at"])
            self.status["duration_seconds"] = (end - start).total_seconds()
        
        if success:
            self.status["current_step"] = "✅ Sync completed successfully!"
            logger.info(f"✅ SYNC COMPLETED - Duration: {self.status['duration_seconds']:.1f}s")
            logger.info(f"📊 FINAL STATS:")
            logger.info(f"   Nodes: {self.status['progress']['nodes_created']} created, {self.status['progress']['nodes_updated']} updated")
            logger.info(f"   Relationships: {self.status['progress']['relationships_created']} created")
        else:
            self.status["current_step"] = "❌ Sync failed with errors"
            logger.error("❌ SYNC FAILED")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        return self.status.copy()
    
    def is_running(self) -> bool:
        """Check if sync is currently running."""
        return self.status["phase"] not in [SyncPhase.IDLE, SyncPhase.COMPLETED, SyncPhase.ERROR]


# Singleton instance
sync_status = SyncStatusTracker()


