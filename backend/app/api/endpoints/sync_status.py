"""
Sync Status API Endpoint.
Provides real-time sync progress monitoring.
"""

import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any

from app.services.sync_status import sync_status

router = APIRouter()
logger = logging.getLogger(__name__)


class SyncStatusResponse(BaseModel):
    """Sync status response."""
    phase: str
    started_at: str | None
    current_step: str
    progress: Dict[str, Any]
    errors: list
    completed_at: str | None
    duration_seconds: float
    is_running: bool


@router.get("/sync-status", response_model=SyncStatusResponse)
async def get_sync_status() -> SyncStatusResponse:
    """
    Get current sync status.
    
    Call this endpoint to monitor sync progress in real-time.
    Poll every 2-5 seconds during sync.
    
    Returns:
        Current sync status with progress details
    """
    status = sync_status.get_status()
    
    return SyncStatusResponse(
        phase=status["phase"],
        started_at=status["started_at"],
        current_step=status["current_step"],
        progress=status["progress"],
        errors=status["errors"],
        completed_at=status["completed_at"],
        duration_seconds=status["duration_seconds"],
        is_running=sync_status.is_running()
    )


