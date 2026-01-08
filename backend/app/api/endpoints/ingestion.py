"""
Document Ingestion API Endpoint.

Handles file uploads with deduplication, storage to MinIO,
and triggers background processing workflow.
Also includes CRM synchronization endpoint.
"""

import hashlib
import logging
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
from app.services.crm_factory import get_crm_provider, is_crm_available
from app.services.graph_store import GraphStoreService, get_graph_store_service
from app.services.storage import MinioService, get_minio_service
from app.services.vector_store import VectorStoreService, get_vector_store_service

router = APIRouter()
logger = logging.getLogger(__name__)


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
    storage_path = f"documents/{doc_id}/{file.filename}"
    
    # Upload to MinIO
    try:
        await minio.upload_file(storage_path, content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to storage: {str(e)}",
        )
    
    # Create database record
    document = KnowledgeDocument(
        id=doc_id,
        filename=file.filename or "unknown",
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
        filename=file.filename or "unknown",
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
    graph_store: Annotated[GraphStoreService, Depends(get_graph_store_service)],
    entity_types: list[str] | None = None,
) -> CRMSyncResponse:
    """
    Synchronisiert CRM-Entities in den Knowledge Graph.
    
    Holt Stammdaten aus dem CRM (z.B. Zoho) und erstellt/aktualisiert
    Nodes im Neo4j Graph. Dies ist der Trigger für nächtliche Syncs.
    
    Args:
        entity_types: Liste der zu synchronisierenden Entity-Typen.
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
    
    # Check if CRM is available
    if not is_crm_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CRM ist nicht konfiguriert. Bitte ACTIVE_CRM_PROVIDER setzen.",
        )
    
    try:
        # Get CRM provider
        provider = get_crm_provider()
        
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="CRM Provider konnte nicht geladen werden",
            )
        
        provider_name = provider.get_provider_name()
        logger.info(f"📞 Using CRM provider: {provider_name}")
        
        # Fetch skeleton data
        logger.info(f"📥 Fetching skeleton data for: {entity_types or 'default types'}")
        skeleton_data = provider.fetch_skeleton_data(entity_types)
        
        if not skeleton_data:
            return CRMSyncResponse(
                status="success",
                entities_synced=0,
                entities_created=0,
                entities_updated=0,
                entity_types=entity_types or [],
                message="No entities found in CRM",
            )
        
        logger.info(f"✅ Fetched {len(skeleton_data)} entities from CRM")
        
        # Sync to Neo4j
        entities_created = 0
        entities_updated = 0
        errors = []
        synced_types = set()
        
        for entity in skeleton_data:
            try:
                source_id = entity.get("source_id")
                name = entity.get("name")
                entity_type = entity.get("type")
                email = entity.get("email")
                related_to = entity.get("related_to")
                relation_type = entity.get("relation_type")
                
                # Additional properties (for Deals, Events, etc.)
                amount = entity.get("amount")
                stage = entity.get("stage")
                status_field = entity.get("status")
                total = entity.get("total")
                start_time = entity.get("start_time")
                
                if not source_id or not name:
                    logger.warning(f"⚠️ Skipping entity with missing data: {entity}")
                    continue
                
                synced_types.add(entity_type)
                
                # MERGE query: Create or update node + relationships
                cypher_query = """
                MERGE (n:CRMEntity {source_id: $source_id})
                ON CREATE SET
                    n.name = $name,
                    n.type = $type,
                    n.email = $email,
                    n.amount = $amount,
                    n.stage = $stage,
                    n.status = $status,
                    n.total = $total,
                    n.start_time = $start_time,
                    n.created_at = datetime(),
                    n.synced_at = datetime(),
                    n.source = $source
                ON MATCH SET
                    n.name = $name,
                    n.type = $type,
                    n.email = $email,
                    n.amount = $amount,
                    n.stage = $stage,
                    n.status = $status,
                    n.total = $total,
                    n.start_time = $start_time,
                    n.synced_at = datetime(),
                    n.source = $source
                
                WITH n
                WHERE $related_to IS NOT NULL
                
                // Merge parent node
                MERGE (p:CRMEntity {source_id: $related_to})
                
                // Create relationships based on relation_type using FOREACH
                WITH n, p
                FOREACH (_ IN CASE WHEN $relation_type = 'OWNED_BY' THEN [1] ELSE [] END |
                    MERGE (p)-[:OWNS]->(n)
                )
                FOREACH (_ IN CASE WHEN $relation_type = 'WORKS_AT' THEN [1] ELSE [] END |
                    MERGE (n)-[:WORKS_AT]->(p)
                )
                FOREACH (_ IN CASE WHEN $relation_type = 'HAS_DEAL' THEN [1] ELSE [] END |
                    MERGE (p)-[:HAS_DEAL]->(n)
                )
                FOREACH (_ IN CASE WHEN $relation_type = 'HAS_EVENT' THEN [1] ELSE [] END |
                    MERGE (p)-[:HAS_EVENT]->(n)
                )
                FOREACH (_ IN CASE WHEN $relation_type = 'HAS_SUBSCRIPTION' THEN [1] ELSE [] END |
                    MERGE (p)-[:HAS_SUBSCRIPTION]->(n)
                )
                FOREACH (_ IN CASE WHEN $relation_type = 'HAS_INVOICE' THEN [1] ELSE [] END |
                    MERGE (p)-[:HAS_INVOICE]->(n)
                )
                
                RETURN n,
                       CASE WHEN n.created_at = n.synced_at THEN 'created' ELSE 'updated' END as action
                """
                
                result = await graph_store.client.execute_query(
                    cypher_query,
                    parameters_={
                        "source_id": source_id,
                        "name": name,
                        "type": entity_type,
                        "email": email,
                        "amount": amount,
                        "stage": stage,
                        "status": status_field,
                        "total": total,
                        "start_time": start_time,
                        "related_to": related_to,
                        "relation_type": relation_type,
                        "source": provider_name,
                    }
                )
                
                # Count created vs updated
                if result and result.records:
                    action = result.records[0].get("action")
                    if action == "created":
                        entities_created += 1
                    else:
                        entities_updated += 1
                
            except Exception as e:
                error_msg = f"Error syncing entity {entity.get('source_id')}: {str(e)}"
                logger.error(f"❌ {error_msg}")
                errors.append(error_msg)
                continue
        
        total_synced = entities_created + entities_updated
        
        logger.info(
            f"✅ CRM Sync completed: "
            f"{total_synced} entities synced "
            f"({entities_created} created, {entities_updated} updated)"
        )
        
        return CRMSyncResponse(
            status="success" if not errors else "partial_success",
            entities_synced=total_synced,
            entities_created=entities_created,
            entities_updated=entities_updated,
            entity_types=list(synced_types),
            message=f"Successfully synced {total_synced} entities from {provider_name}",
            errors=errors[:10],  # Limit to first 10 errors
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ CRM sync failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CRM sync failed: {str(e)}",
        )
