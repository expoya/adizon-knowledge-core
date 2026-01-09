"""
Error Tracker for CRM Sync Operations.

Tracks errors during sync with detailed context for debugging.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class EntityError:
    """Details about a single entity error."""
    entity_id: str
    label: str
    error: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchError:
    """Details about a batch processing error."""
    batch_type: str
    batch_size: int
    error: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorSummary:
    """Summary of all errors during sync."""
    entity_errors: List[EntityError]
    batch_errors: List[BatchError]
    total_entity_errors: int
    total_batch_errors: int
    
    def get_error_messages(self, limit: int = 15) -> List[str]:
        """
        Get formatted error messages for API response.
        
        Args:
            limit: Maximum number of error messages to return
            
        Returns:
            List of formatted error messages
        """
        messages = []
        
        # Add entity errors (first 10)
        for err in self.entity_errors[:10]:
            messages.append(f"{err.label} {err.entity_id}: {err.error}")
        
        # Add batch errors (remaining space)
        remaining = limit - len(messages)
        for err in self.batch_errors[:remaining]:
            messages.append(f"Batch {err.batch_type} ({err.batch_size} items): {err.error}")
        
        return messages[:limit]


class ErrorTracker:
    """
    Tracks errors during CRM sync operations.
    
    Features:
    - Entity-level error tracking
    - Batch-level error tracking
    - Error categorization
    - Detailed context for debugging
    """
    
    def __init__(self):
        """Initialize error tracker."""
        self.entity_errors: List[EntityError] = []
        self.batch_errors: List[BatchError] = []
    
    def track_entity_error(
        self,
        entity_id: str,
        label: str,
        error: Exception,
        context: Dict[str, Any] = None
    ):
        """
        Track an individual entity error.
        
        Args:
            entity_id: Entity source_id
            label: Entity label (e.g., "Lead", "Account")
            error: Exception that occurred
            context: Additional context (e.g., properties, relations)
        """
        entity_error = EntityError(
            entity_id=entity_id,
            label=label,
            error=str(error),
            context=context or {}
        )
        self.entity_errors.append(entity_error)
        
        logger.error(
            f"❌ Entity error: {label} {entity_id}: {error}",
            extra={"entity_id": entity_id, "label": label, "context": context}
        )
    
    def track_batch_error(
        self,
        batch_type: str,
        batch_size: int,
        error: Exception,
        context: Dict[str, Any] = None
    ):
        """
        Track a batch processing error.
        
        Args:
            batch_type: Type of batch (e.g., "Lead nodes", "HAS_OWNER relationships")
            batch_size: Number of items in batch
            error: Exception that occurred
            context: Additional context (e.g., query, parameters)
        """
        batch_error = BatchError(
            batch_type=batch_type,
            batch_size=batch_size,
            error=str(error),
            context=context or {}
        )
        self.batch_errors.append(batch_error)
        
        logger.error(
            f"❌ Batch error: {batch_type} ({batch_size} items): {error}",
            extra={"batch_type": batch_type, "batch_size": batch_size, "context": context}
        )
    
    def get_summary(self) -> ErrorSummary:
        """
        Get error summary.
        
        Returns:
            ErrorSummary with all tracked errors
        """
        return ErrorSummary(
            entity_errors=self.entity_errors,
            batch_errors=self.batch_errors,
            total_entity_errors=len(self.entity_errors),
            total_batch_errors=len(self.batch_errors)
        )
    
    def has_errors(self) -> bool:
        """Check if any errors were tracked."""
        return len(self.entity_errors) > 0 or len(self.batch_errors) > 0
    
    def clear(self):
        """Clear all tracked errors."""
        self.entity_errors.clear()
        self.batch_errors.clear()

