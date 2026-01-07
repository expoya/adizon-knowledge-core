"""
Ingestion Workflow Dispatcher.

This module dispatches document processing tasks to the Trooper Worker microservice.
The actual compute-intensive work (LLM, embeddings, graph extraction) happens in the worker.

Supports multi-tenant mode by passing all connection configs with each request.
"""

import base64
import logging
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def mask_secret(secret: str | None, visible_chars: int = 4) -> str:
    """Mask a secret, showing only first few characters."""
    if not secret:
        return "<empty>"
    if len(secret) <= visible_chars:
        return "*" * len(secret)
    return secret[:visible_chars] + "*" * (len(secret) - visible_chars)


def validate_worker_config(config: dict[str, Any], name: str) -> list[str]:
    """Validate a config dict and return list of missing/empty fields."""
    errors = []
    for key, value in config.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"{name}.{key}")
    return errors


class TrooperDispatchError(Exception):
    """Error dispatching task to Trooper Worker."""
    pass


def get_ontology_content() -> str | None:
    """
    Read and base64-encode the ontology YAML file.

    Returns:
        Base64-encoded ontology content, or None if file not found.
    """
    try:
        ontology_path = Path(settings.ontology_path)
        if not ontology_path.exists():
            logger.warning(f"Ontology file not found: {ontology_path}")
            return None

        with open(ontology_path, "r", encoding="utf-8") as f:
            content = f.read()

        return base64.b64encode(content.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.warning(f"Failed to read ontology file: {e}")
        return None


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

    The request includes all connection configurations so the worker can
    connect to the correct MinIO, PostgreSQL, Neo4j, and Embedding API.

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

    # Read and encode ontology content
    ontology_content = get_ontology_content()
    if ontology_content:
        logger.info(f"   Ontology loaded from: {settings.ontology_path}")
    else:
        logger.warning("   No ontology content - graph extraction may be skipped")

    # Get Worker-specific configs (public URLs with fallback to internal)
    minio_config = settings.get_worker_minio_config()
    postgres_config = settings.get_worker_postgres_config()
    neo4j_config = settings.get_worker_neo4j_config()

    # Build the full request payload with all connection configs
    payload = {
        "document_id": document_id,
        "storage_path": storage_path,
        "filename": filename,
        "callback_url": callback_url,
        # MinIO configuration (public URL for Worker)
        "minio": minio_config,
        # PostgreSQL configuration (public URL for Worker)
        "postgres": postgres_config,
        # Neo4j configuration (public URL for Worker)
        "neo4j": neo4j_config,
        # Embedding/LLM configuration
        "embedding": {
            "api_url": settings.embedding_api_url,
            "api_key": settings.embedding_api_key,
            "model": settings.embedding_model,
            "llm_model": settings.llm_model_name,
        },
        # Ontology content (base64 encoded)
        "ontology_content": ontology_content,
    }

    # Validate configurations
    config_errors = []
    config_errors.extend(validate_worker_config(minio_config, "minio"))
    config_errors.extend(validate_worker_config(postgres_config, "postgres"))
    config_errors.extend(validate_worker_config(neo4j_config, "neo4j"))
    config_errors.extend(validate_worker_config(payload["embedding"], "embedding"))

    if config_errors:
        error_msg = f"Worker configuration incomplete - missing/empty fields: {', '.join(config_errors)}"
        logger.error(error_msg)
        logger.error("   Hint: Set WORKER_* environment variables for public URLs")
        raise TrooperDispatchError(error_msg)

    # Log configuration summary (with masked secrets)
    logger.info("   Worker Configuration:")
    logger.info(f"     MinIO:")
    logger.info(f"       - Endpoint: {minio_config['endpoint']}")
    logger.info(f"       - Bucket: {minio_config['bucket_name']}")
    logger.info(f"       - Secure: {minio_config['secure']}")
    logger.info(f"       - Access Key: {mask_secret(minio_config['access_key'])}")
    logger.info(f"     PostgreSQL:")
    logger.info(f"       - Host: {postgres_config['host']}:{postgres_config['port']}")
    logger.info(f"       - Database: {postgres_config['database']}")
    logger.info(f"       - User: {postgres_config['user']}")
    logger.info(f"       - Password: {mask_secret(postgres_config['password'])}")
    logger.info(f"     Neo4j:")
    logger.info(f"       - URI: {neo4j_config['uri']}")
    logger.info(f"       - User: {neo4j_config['user']}")
    logger.info(f"       - Password: {mask_secret(neo4j_config['password'])}")
    logger.info(f"     Embedding API:")
    logger.info(f"       - URL: {settings.embedding_api_url}")
    logger.info(f"       - Model: {settings.embedding_model}")
    logger.info(f"       - API Key: {mask_secret(settings.embedding_api_key)}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.trooper_url}/ingest",
                json=payload,
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
