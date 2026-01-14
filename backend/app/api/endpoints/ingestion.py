"""
Document Ingestion API Endpoint.

Handles file uploads with deduplication, storage to MinIO,
and triggers background processing workflow.
Also includes CRM synchronization endpoint.
"""

import hashlib
import json
import logging
import os
import re
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.graph.ingestion_workflow import run_ingestion_workflow
from app.models.document import DocumentStatus, KnowledgeDocument
from app.services.crm_factory import get_crm_provider, is_crm_available
from app.services.crm_sync import CRMSyncOrchestrator
from app.services.graph_store import GraphStoreService, get_graph_store_service
from app.services.storage import MinioService, get_minio_service
from app.services.vector_store import VectorStoreService, get_vector_store_service

router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# Security: Filename Sanitization
# =============================================================================

# Whitelist pattern: Only alphanumeric, dots, underscores, hyphens allowed
# This prevents path traversal, command injection, and filesystem issues
SAFE_FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9._-]+$')

# Maximum filename length to prevent DoS and filesystem issues
MAX_FILENAME_LENGTH = 255

# =============================================================================
# Security: File Extension Validation
# =============================================================================

# Dangerous file extensions that should be rejected
# These could be executed or pose security risks if stored
DANGEROUS_EXTENSIONS = {
    # Executables
    'exe', 'dll', 'so', 'dylib',
    # Scripts
    'sh', 'bash', 'bat', 'cmd', 'ps1', 'vbs', 'js', 'jse', 'wsf', 'wsh',
    # Compiled code
    'pyc', 'pyo', 'class', 'jar', 'war', 'ear',
    # Binary/system
    'bin', 'com', 'msi', 'app', 'deb', 'rpm',
    # Potentially dangerous archives (can contain executables)
    'scr', 'pif', 'hta', 'cpl',
}


def validate_file_extension(filename: str) -> tuple[bool, str]:
    """
    Validate that a file extension is not on the dangerous list.

    Args:
        filename: The filename to check

    Returns:
        Tuple of (is_valid, error_message)
    """
    if '.' not in filename:
        return True, ""  # No extension is OK

    ext = filename.rsplit('.', 1)[-1].lower()

    if ext in DANGEROUS_EXTENSIONS:
        return False, f"File extension '.{ext}' is not allowed for security reasons"

    return True, ""


def sanitize_filename(filename: str | None) -> str:
    """
    Sanitize a user-provided filename to prevent security vulnerabilities.

    Security measures:
    1. Extract basename to prevent path traversal (../, ..\\)
    2. Whitelist approach: Only allow safe characters (alphanumeric, ._-)
    3. Replace or remove dangerous characters
    4. Enforce maximum length
    5. Provide fallback for empty/invalid filenames

    Args:
        filename: The raw filename from user upload

    Returns:
        A safe filename that can be used in storage paths

    Raises:
        HTTPException: If filename cannot be sanitized to a valid name
    """
    if not filename:
        return "unnamed_document"

    # Step 1: Extract basename to prevent path traversal
    # os.path.basename handles both Unix (/) and Windows (\\) separators
    safe_name = os.path.basename(filename)

    # Step 2: Remove any remaining path traversal attempts
    # Handle edge cases like "....//", encoded sequences, etc.
    safe_name = safe_name.replace('..', '')
    safe_name = safe_name.replace('/', '')
    safe_name = safe_name.replace('\\', '')

    # Step 3: Apply whitelist - replace non-allowed characters with underscore
    # This handles shell metacharacters ($, `, ;, |, &, etc.),
    # special filesystem chars (<, >, :, ", ?, *),
    # and control characters (\n, \r, \x00, etc.)
    sanitized_chars = []
    for char in safe_name:
        if re.match(r'[a-zA-Z0-9._-]', char):
            sanitized_chars.append(char)
        else:
            # Replace dangerous chars with underscore
            sanitized_chars.append('_')

    safe_name = ''.join(sanitized_chars)

    # Step 4: Clean up multiple consecutive underscores
    safe_name = re.sub(r'_+', '_', safe_name)

    # Step 5: Remove leading/trailing underscores and dots (hidden files prevention)
    safe_name = safe_name.strip('_.')

    # Step 6: Enforce maximum length
    if len(safe_name) > MAX_FILENAME_LENGTH:
        # Preserve extension if present
        if '.' in safe_name:
            name_part, ext = safe_name.rsplit('.', 1)
            max_name_len = MAX_FILENAME_LENGTH - len(ext) - 1
            safe_name = f"{name_part[:max_name_len]}.{ext}"
        else:
            safe_name = safe_name[:MAX_FILENAME_LENGTH]

    # Step 7: Final validation - must have at least one valid character
    if not safe_name or not SAFE_FILENAME_PATTERN.match(safe_name):
        # Generate a safe fallback name
        return "document"

    logger.debug(f"Filename sanitized: '{filename}' -> '{safe_name}'")
    return safe_name


class DocumentResponse(BaseModel):
    """Response model for document operations."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    content_hash: str
    file_size: int
    storage_path: str
    status: str
    created_at: str
    is_duplicate: bool = False
    message: str | None = None


class CRMSyncRequest(BaseModel):
    """Request model for CRM sync operations."""
    
    entity_types: list[str] | None = None


class CRMSyncResponse(BaseModel):
    """Response model for CRM sync operations."""
    
    status: str
    entities_synced: int
    entities_created: int
    entities_updated: int
    entity_types: list[str]
    message: str
    errors: list[str] = []


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: Annotated[UploadFile, File(description="Document to upload (PDF, DOCX, TXT)")],
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    minio: Annotated[MinioService, Depends(get_minio_service)],
) -> DocumentResponse:
    """
    Upload a document for processing.
    
    Process:
    1. Calculate SHA-256 hash for deduplication
    2. Check if document already exists
    3. Upload to MinIO
    4. Create database record
    5. Trigger background processing workflow
    """
    # Read file content
    content = await file.read()
    file_size = len(content)
    
    # Calculate content hash for deduplication
    content_hash = hashlib.sha256(content).hexdigest()
    
    # Check for duplicates
    result = await session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.content_hash == content_hash)
    )
    existing_doc = result.scalar_one_or_none()
    
    if existing_doc:
        return DocumentResponse(
            id=str(existing_doc.id),
            filename=existing_doc.filename,
            content_hash=existing_doc.content_hash,
            file_size=existing_doc.file_size,
            storage_path=existing_doc.storage_path,
            status=existing_doc.status.value,
            created_at=existing_doc.created_at.isoformat(),
            is_duplicate=True,
            message="Document already exists (duplicate detected by content hash)",
        )
    
    # Generate unique ID and storage path
    doc_id = uuid.uuid4()

    # SECURITY: Sanitize filename to prevent path traversal and injection attacks
    # Uses whitelist approach - only alphanumeric, dots, underscores, hyphens allowed
    safe_filename = sanitize_filename(file.filename)
    storage_path = f"documents/{doc_id}/{safe_filename}"

    # Upload to MinIO
    try:
        await minio.upload_file(storage_path, content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to storage: {str(e)}",
        )

    # Create database record
    # Store the sanitized filename, not the raw user input
    document = KnowledgeDocument(
        id=doc_id,
        filename=safe_filename,
        content_hash=content_hash,
        file_size=file_size,
        storage_path=storage_path,
        status=DocumentStatus.PENDING,
    )

    session.add(document)
    await session.commit()
    await session.refresh(document)

    # Trigger background processing
    background_tasks.add_task(
        run_ingestion_workflow,
        document_id=str(doc_id),
        storage_path=storage_path,
        filename=safe_filename,
    )
    
    return DocumentResponse(
        id=str(document.id),
        filename=document.filename,
        content_hash=document.content_hash,
        file_size=document.file_size,
        storage_path=document.storage_path,
        status=document.status.value,
        created_at=document.created_at.isoformat(),
        message="Document uploaded successfully. Processing started.",
    )


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[DocumentResponse]:
    """List all documents."""
    result = await session.execute(select(KnowledgeDocument))
    documents = result.scalars().all()
    
    return [
        DocumentResponse(
            id=str(doc.id),
            filename=doc.filename,
            content_hash=doc.content_hash,
            file_size=doc.file_size,
            storage_path=doc.storage_path,
            status=doc.status.value,
            created_at=doc.created_at.isoformat(),
        )
        for doc in documents
    ]


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> DocumentResponse:
    """Get a specific document by ID."""
    result = await session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == uuid.UUID(document_id))
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    
    return DocumentResponse(
        id=str(document.id),
        filename=document.filename,
        content_hash=document.content_hash,
        file_size=document.file_size,
        storage_path=document.storage_path,
        status=document.status.value,
        created_at=document.created_at.isoformat(),
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    minio: Annotated[MinioService, Depends(get_minio_service)],
    vector_store: Annotated[VectorStoreService, Depends(get_vector_store_service)],
    graph_store: Annotated[GraphStoreService, Depends(get_graph_store_service)],
):
    """
    Delete a document and all associated data.
    
    Removes:
    - Document record from PostgreSQL
    - File from MinIO
    - Vector embeddings from pgvector
    - Graph nodes from Neo4j
    """
    # Get document
    result = await session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == uuid.UUID(document_id))
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    
    # Delete from MinIO
    try:
        await minio.delete_file(document.storage_path)
    except Exception as e:
        # Log but don't fail if file doesn't exist
        print(f"Warning: Could not delete file from MinIO: {e}")
    
    # Delete from vector store
    try:
        await vector_store.delete_by_document_id(document_id)
    except Exception as e:
        print(f"Warning: Could not delete vectors: {e}")
    
    # Delete from graph store
    try:
        await graph_store.delete_by_document_id(document_id)
    except Exception as e:
        print(f"Warning: Could not delete graph nodes: {e}")
    
    # Delete from database
    await session.delete(document)
    await session.commit()


@router.post("/documents/{document_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
async def reprocess_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    Reprocess a document.
    
    Useful when:
    - Processing failed
    - Ontology was updated
    - Want to re-extract entities
    """
    # Get document
    result = await session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == uuid.UUID(document_id))
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    
    # Update status
    document.status = DocumentStatus.PENDING
    document.error_message = None
    await session.commit()
    
    # Trigger background processing
    background_tasks.add_task(
        run_ingestion_workflow,
        document_id=document_id,
        storage_path=document.storage_path,
        filename=document.filename,
    )
    
    return {"message": "Document reprocessing started", "document_id": document_id}


@router.post("/crm-sync", response_model=CRMSyncResponse)
async def sync_crm_entities(
    request: CRMSyncRequest,
    graph_store: Annotated[GraphStoreService, Depends(get_graph_store_service)],
) -> CRMSyncResponse:
    """
    Synchronisiert CRM-Entities in den Knowledge Graph.
    
    Holt Stammdaten aus dem CRM (z.B. Zoho) und erstellt/aktualisiert
    Nodes im Neo4j Graph. Dies ist der Trigger für nächtliche Syncs.
    
    Args:
        request: CRMSyncRequest mit entity_types Liste.
                 Default: ["Users", "Accounts", "Contacts", "Leads"]
    
    Returns:
        CRMSyncResponse mit Statistiken
        
    Example:
        POST /api/v1/ingestion/crm-sync
        {
            "entity_types": ["Contacts", "Accounts"]
        }
    """
    logger.info("🔄 CRM Sync: Starting synchronization")
    logger.debug(f"Request entity_types: {request.entity_types}")
    
    # Check if CRM is available
    logger.debug("Checking CRM availability...")
    if not is_crm_available():
        logger.error("❌ CRM not available - ACTIVE_CRM_PROVIDER not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CRM ist nicht konfiguriert. Bitte ACTIVE_CRM_PROVIDER setzen.",
        )
    logger.debug("✓ CRM is available")
    
    try:
        # Get CRM provider
        logger.debug("Getting CRM provider...")
        provider = get_crm_provider()
        
        if not provider:
            logger.error("❌ CRM provider is None")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="CRM Provider konnte nicht geladen werden",
            )
        
        provider_name = provider.get_provider_name()
        logger.info(f"📞 Using CRM provider: {provider_name}")
        logger.debug(f"Provider type: {type(provider).__name__}")
        
        # Create orchestrator and execute sync
        logger.debug("Creating CRMSyncOrchestrator...")
        orchestrator = CRMSyncOrchestrator(graph_store)
        logger.debug("✓ Orchestrator created")
        
        logger.info("🚀 Starting sync workflow...")
        result = await orchestrator.sync(provider, request.entity_types)
        logger.info(f"✅ Sync completed: {result.status}")
        
        # Convert to API response format
        return CRMSyncResponse(
            status=result.status,
            entities_synced=result.entities_synced,
            entities_created=result.entities_created,
            entities_updated=result.entities_updated,
            entity_types=result.entity_types,
            message=result.message,
            errors=result.errors
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ CRM sync failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CRM sync failed: {str(e)}",
        )
