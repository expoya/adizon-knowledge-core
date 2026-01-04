"""
Ingestion Workflow Dispatcher.

This module dispatches document processing tasks to the Trooper Worker microservice.
The actual compute-intensive work (LLM, embeddings, graph extraction) happens in the worker.
"""

import logging

import httpx

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class TrooperDispatchError(Exception):
    """Error dispatching task to Trooper Worker."""
    pass


async def run_ingestion_workflow(
    document_id: str,
    storage_path: str,
    filename: str,
) -> dict:
    """
    Dispatch document ingestion to the Trooper Worker.

    This function sends an HTTP request to the Trooper Worker microservice,
    which handles all compute-intensive operations (document loading, chunking,
    embedding generation, LLM-based graph extraction).

    Args:
        document_id: UUID of the document
        storage_path: Path to the document in MinIO
        filename: Original filename

    Returns:
        Response from the Trooper Worker

    Raises:
        TrooperDispatchError: If the dispatch fails
    """
    # Construct callback URL for status updates
    callback_url = f"{settings.public_url}/api/v1/documents/{document_id}/status"
    
    logger.info(f"Dispatching ingestion task to Trooper: {filename}")
    logger.info(f"   Document ID: {document_id}")
    logger.info(f"   Trooper URL: {settings.trooper_url}")
    logger.info(f"   Callback URL: {callback_url}")

    # Build headers with optional auth token
    headers = {}
    if settings.trooper_auth_token:
        headers["Authorization"] = f"Bearer {settings.trooper_auth_token}"
        logger.info("   Using auth token for Trooper request")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.trooper_url}/ingest",
                json={
                    "document_id": document_id,
                    "storage_path": storage_path,
                    "filename": filename,
                    "callback_url": callback_url,
                },
                headers=headers,
                timeout=30.0,
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"   ✓ Task dispatched successfully: {result.get('status')}")
                return result
            else:
                error_msg = f"Trooper returned status {response.status_code}: {response.text}"
                logger.error(f"   ✗ Dispatch failed: {error_msg}")
                raise TrooperDispatchError(error_msg)

    except httpx.ConnectError as e:
        error_msg = f"Cannot connect to Trooper Worker at {settings.trooper_url}: {e}"
        logger.error(f"   ✗ Connection error: {error_msg}")
        raise TrooperDispatchError(error_msg)

    except httpx.TimeoutException as e:
        error_msg = f"Timeout connecting to Trooper Worker: {e}"
        logger.error(f"   ✗ Timeout: {error_msg}")
        raise TrooperDispatchError(error_msg)

    except Exception as e:
        error_msg = f"Unexpected error dispatching to Trooper: {e}"
        logger.error(f"   ✗ Error: {error_msg}")
        raise TrooperDispatchError(error_msg)
