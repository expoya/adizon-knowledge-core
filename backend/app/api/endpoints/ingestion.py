"""
Document Ingestion API Endpoint.

Handles file uploads with deduplication, storage to MinIO,
and triggers background processing workflow.
Also includes CRM synchronization endpoint.
"""

import hashlib
import json
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
        logger.info(f"📥 Fetching skeleton data for: {request.entity_types or 'default types'}")
        skeleton_data = await provider.fetch_skeleton_data(request.entity_types)
        
        if not skeleton_data:
            return CRMSyncResponse(
                status="success",
                entities_synced=0,
                entities_created=0,
                entities_updated=0,
                entity_types=request.entity_types or [],
                message="No entities found in CRM",
            )
        
        logger.info(f"✅ Fetched {len(skeleton_data)} entities from CRM")
        
        # Helper: Sanitize properties for Neo4j (primitives only)
        def _sanitize_properties(props: dict) -> dict:
            """
            Sanitize properties for Neo4j storage.
            
            Neo4j properties must be primitives (str, int, float, bool) or arrays thereof.
            Converts dicts to JSON strings or extracts IDs from lookup fields.
            """
            sanitized = {}
            for key, value in props.items():
                if value is None:
                    continue  # Skip None values
                elif isinstance(value, dict):
                    # Zoho lookup field: {"id": "...", "name": "..."}
                    # Extract ID if present, otherwise serialize to JSON
                    if "id" in value:
                        sanitized[f"{key}_id"] = str(value["id"])
                        if "name" in value:
                            sanitized[f"{key}_name"] = str(value["name"])
                    else:
                        # Generic dict: serialize to JSON string
                        sanitized[key] = json.dumps(value)
                elif isinstance(value, list):
                    # Check if list contains dicts
                    if value and isinstance(value[0], dict):
                        # Array of dicts: serialize to JSON string
                        sanitized[key] = json.dumps(value)
                    else:
                        # Primitive array: keep as-is
                        sanitized[key] = value
                elif isinstance(value, (str, int, float, bool)):
                    # Primitive: keep as-is
                    sanitized[key] = value
                else:
                    # Unknown type: convert to string
                    sanitized[key] = str(value)
            return sanitized
        
        # Sync to Neo4j with structured graph schema
        entities_created = 0
        entities_updated = 0
        errors = []
        synced_types = set()
        failed_entities = []  # Track failed entities with details
        
        # Step 1: Group entities by label for batch processing
        entities_by_label = {}
        all_relations = []
        
        for entity in skeleton_data:
            try:
                label = entity.get("label")
                if not label:
                    logger.warning(f"⚠️ Skipping entity without label: {entity}")
                    continue
                
                synced_types.add(label)
                
                # Group by label
                if label not in entities_by_label:
                    entities_by_label[label] = []
                
                # Sanitize properties before storing
                raw_props = entity.get("properties", {})
                sanitized_props = _sanitize_properties(raw_props)
                
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
                        "direction": rel["direction"]
                    })
                    
            except Exception as e:
                entity_id = entity.get("source_id", "unknown")
                error_msg = f"Entity {entity_id}: {str(e)}"
                logger.error(f"❌ Error processing entity: {error_msg}")
                errors.append(error_msg)
                failed_entities.append({
                    "source_id": entity_id,
                    "label": entity.get("label"),
                    "error": str(e)
                })
                continue
        
        logger.info(f"📊 Grouped into {len(entities_by_label)} labels with {len(all_relations)} relations")
        
        # Step 2: Create nodes per label (batch UNWIND)
        for label, entities in entities_by_label.items():
            try:
                # Sanitize label (alphanumeric only)
                safe_label = ''.join(c for c in label if c.isalnum() or c == '_')
                
                # Build dynamic MERGE query with label
                # Note: Labels can't be parameterized in Cypher, so we use string formatting
                # This is safe because we sanitize the label above
                cypher_query = f"""
                UNWIND $batch as row
                MERGE (n:{safe_label} {{source_id: row.source_id}})
                ON CREATE SET
                    n += row.properties,
                    n.created_at = datetime(),
                    n.synced_at = datetime(),
                    n.source = $source
                ON MATCH SET
                    n += row.properties,
                    n.synced_at = datetime()
                RETURN count(n) as count,
                       sum(CASE WHEN n.created_at = n.synced_at THEN 1 ELSE 0 END) as created,
                       sum(CASE WHEN n.created_at <> n.synced_at THEN 1 ELSE 0 END) as updated
                """
                
                result = await graph_store.query(
                    cypher_query,
                    parameters={
                        "batch": entities,
                        "source": provider_name
                    }
                )
                
                if result and len(result) > 0:
                    entities_created += result[0].get("created", 0)
                    entities_updated += result[0].get("updated", 0)
                    logger.info(f"  ✅ {label}: {result[0].get('count', 0)} nodes ({result[0].get('created', 0)} created)")
                    
            except Exception as e:
                error_msg = f"Error syncing {label} nodes ({len(entities)} entities): {str(e)}"
                logger.error(f"❌ {error_msg}")
                errors.append(error_msg)
                # Track all entities in this batch as failed
                for entity in entities:
                    failed_entities.append({
                        "source_id": entity.get("source_id"),
                        "label": label,
                        "error": f"Batch sync failed: {str(e)}"
                    })
                continue
        
        # Step 3: Create relationships grouped by edge type
        relations_by_edge = {}
        for rel in all_relations:
            edge_type = rel["edge_type"]
            if edge_type not in relations_by_edge:
                relations_by_edge[edge_type] = []
            relations_by_edge[edge_type].append(rel)
        
        logger.info(f"🔗 Creating {len(all_relations)} relationships across {len(relations_by_edge)} edge types")
        
        for edge_type, relations in relations_by_edge.items():
            try:
                # Sanitize edge type
                safe_edge = ''.join(c for c in edge_type if c.isalnum() or c == '_')
                
                # Separate by direction
                outgoing = [r for r in relations if r["direction"] == "OUTGOING"]
                incoming = [r for r in relations if r["direction"] == "INCOMING"]
                
                # Create OUTGOING relationships: (source)-[edge]->(target)
                if outgoing:
                    cypher_query = f"""
                    UNWIND $batch as row
                    MATCH (a {{source_id: row.source_id}})
                    MERGE (b:CRMEntity {{source_id: row.target_id}})
                    MERGE (a)-[r:{safe_edge}]->(b)
                    ON CREATE SET r.created_at = datetime()
                    RETURN count(r) as count
                    """
                    
                    result = await graph_store.query(
                        cypher_query,
                        parameters={"batch": outgoing}
                    )
                    
                    if result and len(result) > 0:
                        logger.info(f"  ✅ {edge_type} (OUTGOING): {result[0].get('count', 0)} edges")
                
                # Create INCOMING relationships: (target)-[edge]->(source)
                if incoming:
                    cypher_query = f"""
                    UNWIND $batch as row
                    MATCH (a {{source_id: row.source_id}})
                    MERGE (b:CRMEntity {{source_id: row.target_id}})
                    MERGE (b)-[r:{safe_edge}]->(a)
                    ON CREATE SET r.created_at = datetime()
                    RETURN count(r) as count
                    """
                    
                    result = await graph_store.query(
                        cypher_query,
                        parameters={"batch": incoming}
                    )
                    
                    if result and len(result) > 0:
                        logger.info(f"  ✅ {edge_type} (INCOMING): {result[0].get('count', 0)} edges")
                    
            except Exception as e:
                error_msg = f"Error creating {edge_type} relationships: {str(e)}"
                logger.error(f"❌ {error_msg}")
                errors.append(error_msg)
                continue
        
        total_synced = entities_created + entities_updated
        total_failed = len(failed_entities)
        
        # Build detailed status message
        if total_failed > 0:
            status_msg = (
                f"Partial sync completed: {total_synced} entities synced "
                f"({entities_created} created, {entities_updated} updated), "
                f"{total_failed} failed"
            )
        else:
            status_msg = (
                f"CRM Sync completed successfully: {total_synced} entities synced "
                f"({entities_created} created, {entities_updated} updated)"
            )
        
        logger.info(f"✅ {status_msg}")
        
        # Build error details with IDs
        error_details = []
        if failed_entities:
            # Group failures by error type
            for failure in failed_entities[:10]:  # Limit to first 10
                error_details.append(
                    f"{failure['label']} {failure['source_id']}: {failure['error']}"
                )
        
        # Add generic errors
        error_details.extend(errors[:5])  # Add up to 5 generic errors
        
        return CRMSyncResponse(
            status="success" if not errors and not failed_entities else "partial_success",
            entities_synced=total_synced,
            entities_created=entities_created,
            entities_updated=entities_updated,
            entity_types=list(synced_types),
            message=status_msg,
            errors=error_details[:15],  # Limit total errors to 15
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ CRM sync failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CRM sync failed: {str(e)}",
        )
