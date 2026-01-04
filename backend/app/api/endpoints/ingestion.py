"""
Document Ingestion API Endpoint.

Handles file uploads with deduplication, storage to MinIO,
and triggers background processing workflow.
"""

import hashlib
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
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.graph.ingestion_workflow import run_ingestion_workflow
from app.models.document import DocumentStatus, KnowledgeDocument
from app.services.graph_store import GraphStoreService, get_graph_store_service
from app.services.storage import MinioService, get_minio_service
from app.services.vector_store import VectorStoreService, get_vector_store_service

router = APIRouter()


class DocumentResponse(BaseModel):
    """Response model for document operations."""

    id: str
    filename: str
    content_hash: str
    file_size: int
    storage_path: str
    status: str
    created_at: str
    is_duplicate: bool = False
    message: str | None = None

    class Config:
        from_attributes = True


def compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(content).hexdigest()


def generate_storage_path(filename: str) -> str:
    """
    Generate a unique storage path for the file.
    
    Format: raw/{year}/{month}/{uuid}_{filename}
    """
    now = datetime.utcnow()
    unique_id = uuid.uuid4().hex[:8]
    # Sanitize filename (remove path separators)
    safe_filename = filename.replace("/", "_").replace("\\", "_")
    return f"raw/{now.year}/{now.month:02d}/{unique_id}_{safe_filename}"


async def process_document_background(
    document_id: str,
    storage_path: str,
    filename: str,
) -> None:
    """
    Background task to process document through ingestion workflow.
    """
    print(f"🚀 [BACKGROUND] Starting ingestion for document {document_id} ({filename})")
    try:
        result = await run_ingestion_workflow(
            document_id=document_id,
            storage_path=storage_path,
            filename=filename,
        )
        print(f"✓ [BACKGROUND] Document {document_id} processed: {result.get('status')}")
    except Exception as e:
        print(f"✗ [BACKGROUND] Document {document_id} processing failed: {e}")
        import traceback
        traceback.print_exc()
        # Error handling is done in the workflow's finalize node


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: Annotated[UploadFile, File(description="Document file to upload")],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    minio: Annotated[MinioService, Depends(get_minio_service)],
    background_tasks: BackgroundTasks,
) -> DocumentResponse:
    """
    Upload a document for processing.
    
    The upload process:
    1. Read file content and compute SHA-256 hash
    2. Check if document with same hash already exists (deduplication)
       - If YES: Return existing document without re-uploading
       - If NO: Upload to MinIO and save metadata to Postgres
    3. Trigger background ingestion workflow
    4. Return document metadata immediately
    
    Duplicate documents are detected by content hash and not re-uploaded.
    """
    # Read file content
    content = await file.read()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file uploaded",
        )

    file_size = len(content)
    
    # Compute SHA-256 hash for deduplication
    content_hash = compute_file_hash(content)

    # Check for existing document with same hash
    existing_query = await session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.content_hash == content_hash)
    )
    existing_doc = existing_query.scalar_one_or_none()

    if existing_doc:
        # Document already exists - return it without re-uploading
        return DocumentResponse(
            id=str(existing_doc.id),
            filename=existing_doc.filename,
            content_hash=existing_doc.content_hash,
            file_size=existing_doc.file_size,
            storage_path=existing_doc.storage_path,
            status=existing_doc.status.value,
            created_at=existing_doc.created_at.isoformat(),
            is_duplicate=True,
            message="Document with identical content already exists",
        )

    # Generate storage path
    filename = file.filename or "unknown"
    storage_path = generate_storage_path(filename)

    # Upload to MinIO
    try:
        await minio.upload_bytes(
            content=content,
            object_name=storage_path,
            content_type=file.content_type or "application/octet-stream",
            filename=filename,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload to storage: {str(e)}",
        )

    # Create database record with PENDING status
    document = KnowledgeDocument(
        filename=filename,
        content_hash=content_hash,
        file_size=file_size,
        storage_path=storage_path,
        status=DocumentStatus.PENDING,
    )
    session.add(document)
    await session.flush()  # Get the generated ID

    # Get the document ID as string for background task
    document_id = str(document.id)

    # Commit the transaction BEFORE starting background task
    await session.commit()

    # Schedule background processing
    background_tasks.add_task(
        process_document_background,
        document_id=document_id,
        storage_path=storage_path,
        filename=filename,
    )

    return DocumentResponse(
        id=document_id,
        filename=document.filename,
        content_hash=document.content_hash,
        file_size=document.file_size,
        storage_path=document.storage_path,
        status=document.status.value,
        created_at=document.created_at.isoformat(),
        is_duplicate=False,
        message="Document uploaded. Processing started in background.",
    )


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    status_filter: DocumentStatus | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[DocumentResponse]:
    """
    List all documents with optional status filter.
    """
    query = select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
    
    if status_filter:
        query = query.where(KnowledgeDocument.status == status_filter)
    
    query = query.limit(limit).offset(offset)
    
    result = await session.execute(query)
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
    """
    Get a single document by ID.
    """
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID format",
        )

    result = await session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == doc_uuid)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )

    return DocumentResponse(
        id=str(document.id),
        filename=document.filename,
        content_hash=document.content_hash,
        file_size=document.file_size,
        storage_path=document.storage_path,
        status=document.status.value,
        created_at=document.created_at.isoformat(),
        message=document.error_message,
    )


@router.post("/documents/{document_id}/reprocess", response_model=DocumentResponse)
async def reprocess_document(
    document_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    background_tasks: BackgroundTasks,
) -> DocumentResponse:
    """
    Trigger reprocessing of an existing document.
    
    Useful for documents that failed or need re-indexing.
    """
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID format",
        )

    result = await session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == doc_uuid)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )

    # Reset status to PENDING
    document.status = DocumentStatus.PENDING
    document.error_message = None
    await session.flush()

    # Schedule background processing
    background_tasks.add_task(
        process_document_background,
        document_id=str(document.id),
        storage_path=document.storage_path,
        filename=document.filename,
    )

    return DocumentResponse(
        id=str(document.id),
        filename=document.filename,
        content_hash=document.content_hash,
        file_size=document.file_size,
        storage_path=document.storage_path,
        status=document.status.value,
        created_at=document.created_at.isoformat(),
        message="Reprocessing started in background.",
    )


class StatusUpdateRequest(BaseModel):
    """Request model for status updates from Trooper Worker."""
    status: str
    error_message: str | None = None


class StatusUpdateResponse(BaseModel):
    """Response model for status update confirmation."""
    document_id: str
    status: str
    message: str


class DeleteDocumentResponse(BaseModel):
    """Response model for document deletion."""
    id: str
    filename: str
    vectors_deleted: bool
    graph_nodes_deleted: int
    storage_deleted: bool
    message: str


@router.post("/documents/{document_id}/status", response_model=StatusUpdateResponse)
async def update_document_status(
    document_id: str,
    request: StatusUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> StatusUpdateResponse:
    """
    Update document status (callback from Trooper Worker).

    This endpoint is called by the Trooper Worker when document processing
    completes or fails. It updates the document status in the database.

    Args:
        document_id: UUID of the document
        request: StatusUpdateRequest with new status and optional error message

    Returns:
        StatusUpdateResponse confirming the update
    """
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID format",
        )

    result = await session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == doc_uuid)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )

    # Map status string to enum
    status_map = {
        "INDEXED": DocumentStatus.INDEXED,
        "ERROR": DocumentStatus.ERROR,
        "PENDING": DocumentStatus.PENDING,
    }

    new_status = status_map.get(request.status.upper())
    if not new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {request.status}. Must be one of: INDEXED, ERROR, PENDING",
        )

    document.status = new_status
    document.error_message = request.error_message
    await session.commit()

    return StatusUpdateResponse(
        document_id=document_id,
        status=new_status.value,
        message=f"Document status updated to {new_status.value}",
    )


@router.delete("/documents/{document_id}", response_model=DeleteDocumentResponse)
async def delete_document(
    document_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    minio: Annotated[MinioService, Depends(get_minio_service)],
    vector_store: Annotated[VectorStoreService, Depends(get_vector_store_service)],
    graph_store: Annotated[GraphStoreService, Depends(get_graph_store_service)],
) -> DeleteDocumentResponse:
    """
    Delete a document and all associated data.

    This removes:
    1. Vector embeddings from PGVector
    2. Graph nodes from Neo4j
    3. File from MinIO storage
    4. Metadata from PostgreSQL
    """
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID format",
        )

    # Get document from database
    result = await session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == doc_uuid)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )

    filename = document.filename
    storage_path = document.storage_path

    # 1. Delete vectors from PGVector
    vectors_deleted = False
    try:
        await vector_store.delete_by_filename(filename)
        vectors_deleted = True
    except Exception as e:
        print(f"Warning: Failed to delete vectors for {filename}: {e}")

    # 2. Delete graph nodes from Neo4j
    graph_nodes_deleted = 0
    try:
        graph_nodes_deleted = await graph_store.delete_by_document_id(document_id)
    except Exception as e:
        print(f"Warning: Failed to delete graph nodes for {filename}: {e}")

    # 3. Delete file from MinIO
    storage_deleted = False
    try:
        await minio.delete_file(storage_path)
        storage_deleted = True
    except Exception as e:
        print(f"Warning: Failed to delete file from storage: {e}")

    # 4. Delete metadata from PostgreSQL
    await session.delete(document)
    await session.commit()

    return DeleteDocumentResponse(
        id=document_id,
        filename=filename,
        vectors_deleted=vectors_deleted,
        graph_nodes_deleted=graph_nodes_deleted,
        storage_deleted=storage_deleted,
        message=f"Document '{filename}' and associated data deleted successfully.",
    )
