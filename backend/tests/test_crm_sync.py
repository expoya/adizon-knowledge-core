"""
Tests for CRM Sync Services.

Unit tests for the refactored CRM sync components.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.crm_sync import (
    PropertySanitizer,
    ErrorTracker,
    NodeBatchProcessor,
    RelationshipProcessor,
    CRMSyncOrchestrator
)


class TestPropertySanitizer:
    """Tests for PropertySanitizer."""
    
    def test_sanitize_lookup_field(self):
        """Test sanitization of Zoho lookup fields."""
        sanitizer = PropertySanitizer()
        props = {"Owner": {"id": "123", "name": "John Doe"}}
        
        result = sanitizer.sanitize(props)
        
        assert result["owner_id"] == "123"
        assert result["owner_name"] == "John Doe"
    
    def test_sanitize_primitive(self):
        """Test that primitives pass through unchanged."""
        sanitizer = PropertySanitizer()
        props = {"name": "Test", "amount": 1000, "active": True}
        
        result = sanitizer.sanitize(props)
        
        assert result["name"] == "Test"
        assert result["amount"] == 1000
        assert result["active"] is True
    
    def test_sanitize_none_values(self):
        """Test that None values are skipped."""
        sanitizer = PropertySanitizer()
        props = {"name": "Test", "email": None}
        
        result = sanitizer.sanitize(props)
        
        assert "name" in result
        assert "email" not in result
    
    def test_sanitize_list_of_dicts(self):
        """Test that list of dicts is serialized to JSON."""
        sanitizer = PropertySanitizer()
        props = {"tags": [{"name": "tag1"}, {"name": "tag2"}]}
        
        result = sanitizer.sanitize(props)
        
        assert isinstance(result["tags"], str)
        assert "tag1" in result["tags"]


class TestErrorTracker:
    """Tests for ErrorTracker."""
    
    def test_track_entity_error(self):
        """Test tracking entity errors."""
        tracker = ErrorTracker()
        
        tracker.track_entity_error("lead_123", "Lead", Exception("Test error"))
        
        summary = tracker.get_summary()
        assert summary.total_entity_errors == 1
        assert summary.entity_errors[0].entity_id == "lead_123"
        assert summary.entity_errors[0].label == "Lead"
    
    def test_track_batch_error(self):
        """Test tracking batch errors."""
        tracker = ErrorTracker()
        
        tracker.track_batch_error("Lead nodes", 50, Exception("Batch failed"))
        
        summary = tracker.get_summary()
        assert summary.total_batch_errors == 1
        assert summary.batch_errors[0].batch_type == "Lead nodes"
        assert summary.batch_errors[0].batch_size == 50
    
    def test_has_errors(self):
        """Test error detection."""
        tracker = ErrorTracker()
        
        assert not tracker.has_errors()
        
        tracker.track_entity_error("lead_123", "Lead", Exception("Test"))
        
        assert tracker.has_errors()
    
    def test_clear_errors(self):
        """Test clearing errors."""
        tracker = ErrorTracker()
        
        tracker.track_entity_error("lead_123", "Lead", Exception("Test"))
        tracker.clear()
        
        assert not tracker.has_errors()


@pytest.mark.asyncio
class TestNodeBatchProcessor:
    """Tests for NodeBatchProcessor."""
    
    async def test_process_nodes_success(self):
        """Test successful node processing."""
        # Mock graph store
        graph_store = AsyncMock()
        graph_store.query.return_value = [
            {"count": 10, "created": 5, "updated": 5}
        ]
        
        processor = NodeBatchProcessor(graph_store)
        
        entities_by_label = {
            "Lead": [
                {"source_id": "lead_1", "properties": {"name": "Test"}},
                {"source_id": "lead_2", "properties": {"name": "Test2"}}
            ]
        }
        
        result = await processor.process_nodes(entities_by_label, "zoho")
        
        assert result.created == 5
        assert result.updated == 5
        assert "Lead" in result.labels_processed
        assert graph_store.query.called


@pytest.mark.asyncio
class TestRelationshipProcessor:
    """Tests for RelationshipProcessor."""
    
    async def test_process_relationships_success(self):
        """Test successful relationship processing."""
        # Mock graph store
        graph_store = AsyncMock()
        graph_store.query.return_value = [{"count": 5}]
        
        processor = RelationshipProcessor(graph_store)
        
        relations = [
            {
                "source_id": "lead_1",
                "target_id": "user_1",
                "edge_type": "HAS_OWNER",
                "target_label": "User",
                "direction": "OUTGOING"
            }
        ]
        
        result = await processor.process_relationships(relations)
        
        assert result.created == 5
        assert graph_store.query.called
    
    def test_group_relations(self):
        """Test relation grouping."""
        graph_store = AsyncMock()
        processor = RelationshipProcessor(graph_store)
        
        relations = [
            {
                "source_id": "lead_1",
                "target_id": "user_1",
                "edge_type": "HAS_OWNER",
                "target_label": "User",
                "direction": "OUTGOING"
            },
            {
                "source_id": "lead_2",
                "target_id": "user_1",
                "edge_type": "HAS_OWNER",
                "target_label": "User",
                "direction": "OUTGOING"
            }
        ]
        
        grouped = processor._group_relations(relations)
        
        key = ("HAS_OWNER", "User", "OUTGOING")
        assert key in grouped
        assert len(grouped[key]) == 2


@pytest.mark.asyncio
class TestCRMSyncOrchestrator:
    """Tests for CRMSyncOrchestrator."""
    
    async def test_sync_success(self):
        """Test successful sync workflow."""
        # Mock graph store
        graph_store = AsyncMock()
        graph_store.get_last_sync_time.return_value = None
        graph_store.query.return_value = [
            {"count": 10, "created": 10, "updated": 0}
        ]
        
        # Mock provider
        provider = AsyncMock()
        provider.get_provider_name.return_value = "zoho"
        provider.fetch_skeleton_data.return_value = [
            {
                "label": "Lead",
                "source_id": "lead_1",
                "properties": {"name": "Test Lead"},
                "relations": []
            }
        ]
        
        orchestrator = CRMSyncOrchestrator(graph_store)
        
        result = await orchestrator.sync(provider, entity_types=["Leads"])
        
        assert result.status == "success"
        assert result.entities_created > 0
        assert provider.fetch_skeleton_data.called

