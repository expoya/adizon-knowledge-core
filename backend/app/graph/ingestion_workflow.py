"""
LangGraph Ingestion Workflow for document processing.

This workflow handles:
1. Loading documents from MinIO (PDF, DOCX, TXT)
2. Splitting into chunks
3. Storing embeddings in PGVector
4. Extracting entities for Neo4j via LLM
5. Updating document status
"""

import os
import re
import tempfile
from typing import List, TypedDict

from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import END, StateGraph

from app.core.config import get_settings
from app.db.session import async_session_maker
from app.models.document import DocumentStatus, KnowledgeDocument
from app.services.graph_store import get_graph_store_service
from app.services.storage import get_minio_service
from app.services.vector_store import get_vector_store_service

settings = get_settings()


class IngestionState(TypedDict):
    """State for the ingestion workflow."""

    document_id: str
    storage_path: str
    filename: str
    text_chunks: List[Document]
    entities: List[dict]
    relationships: List[dict]
    vector_ids: List[str]
    error: str | None
    status: str


def sanitize_text(text: str) -> str:
    """
    Sanitize text for PostgreSQL compatibility.
    
    Removes:
    - NUL bytes (0x00) which PostgreSQL text fields cannot contain
    - Other problematic control characters
    """
    if not text:
        return ""
    
    # Remove NUL bytes (critical for PostgreSQL)
    text = text.replace("\x00", "")
    
    # Remove other non-printable control characters (except common whitespace)
    # Keep: \t (tab), \n (newline), \r (carriage return)
    text = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    return text


def sanitize_documents(documents: List[Document]) -> List[Document]:
    """
    Sanitize all documents' page_content for PostgreSQL compatibility.
    """
    for doc in documents:
        doc.page_content = sanitize_text(doc.page_content)
    return documents


def get_llm() -> ChatOpenAI:
    """
    Get the configured LLM for graph extraction.
    Uses the Trooper server with adizon-ministral model.
    """
    return ChatOpenAI(
        openai_api_base=settings.embedding_api_url,
        openai_api_key=settings.embedding_api_key,
        model_name=settings.llm_model_name,
        temperature=0,
    )


async def load_node(state: IngestionState) -> dict:
    """
    Load document from MinIO and extract text.
    
    Supports:
    - PDF files (.pdf) via PyPDFLoader
    - Word files (.docx) via Docx2txtLoader
    - Text files (.txt, .md, etc.) via TextLoader or direct decode
    """
    try:
        minio = get_minio_service()
        content = await minio.download_file(state["storage_path"])

        filename_lower = state["filename"].lower()
        documents: List[Document] = []
        tmp_path: str | None = None

        try:
            # Determine file type and use appropriate loader
            if filename_lower.endswith(".pdf"):
                # PDF files
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                
                loader = PyPDFLoader(tmp_path)
                documents = loader.load()

            elif filename_lower.endswith(".docx"):
                # Word documents
                with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                
                loader = Docx2txtLoader(tmp_path)
                documents = loader.load()

            elif filename_lower.endswith(".txt") or filename_lower.endswith(".md"):
                # Plain text files - use TextLoader for better handling
                with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode='wb') as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                
                loader = TextLoader(tmp_path, encoding="utf-8")
                try:
                    documents = loader.load()
                except UnicodeDecodeError:
                    # Fallback to latin-1
                    loader = TextLoader(tmp_path, encoding="latin-1")
                    documents = loader.load()

            else:
                # Fallback: try to decode as text
                try:
                    text = content.decode("utf-8")
                except UnicodeDecodeError:
                    text = content.decode("latin-1")

                documents = [
                    Document(
                        page_content=text,
                        metadata={
                            "source": state["storage_path"],
                            "filename": state["filename"],
                        },
                    )
                ]

        finally:
            # Clean up temp file
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

        # Add metadata to all documents
        for doc in documents:
            doc.metadata["document_id"] = state["document_id"]
            doc.metadata["filename"] = state["filename"]

        # Sanitize text to remove NUL bytes and problematic characters
        documents = sanitize_documents(documents)

        return {
            "text_chunks": documents,
            "status": "loaded",
        }

    except Exception as e:
        return {
            "error": f"Failed to load document: {str(e)}",
            "status": "error",
        }


async def split_node(state: IngestionState) -> dict:
    """
    Split loaded documents into smaller chunks.
    """
    if state.get("error"):
        return {}

    try:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=3000,
            chunk_overlap=300,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        all_chunks: List[Document] = []
        for doc in state["text_chunks"]:
            chunks = splitter.split_documents([doc])
            all_chunks.extend(chunks)

        # Add chunk index to metadata and sanitize again (just to be safe)
        for i, chunk in enumerate(all_chunks):
            chunk.metadata["chunk_index"] = i
            # Final sanitization pass
            chunk.page_content = sanitize_text(chunk.page_content)

        return {
            "text_chunks": all_chunks,
            "status": "split",
        }

    except Exception as e:
        return {
            "error": f"Failed to split document: {str(e)}",
            "status": "error",
        }


async def vector_node(state: IngestionState) -> dict:
    """
    Store document chunks in PGVector.
    """
    if state.get("error"):
        return {}

    try:
        vector_store = get_vector_store_service()
        ids = await vector_store.add_documents(
            chunks=state["text_chunks"],
            document_id=state["document_id"],
        )

        return {
            "vector_ids": ids,
            "status": "vectorized",
        }

    except Exception as e:
        return {
            "error": f"Failed to store vectors: {str(e)}",
            "status": "error",
        }


async def graph_node(state: IngestionState) -> dict:
    """
    Extract entities and relationships using LLM and store in Neo4j.
    
    Uses LLMGraphTransformer with the local Trooper/Ministral model.
    Falls back gracefully if extraction fails - vectors are still indexed.
    """
    if state.get("error"):
        return {}

    entities: List[dict] = []
    relationships: List[dict] = []

    try:
        # Import here to avoid import errors if langchain-experimental not installed
        from langchain_experimental.graph_transformers import LLMGraphTransformer
        
        # Initialize LLM with Trooper endpoint
        llm = get_llm()
        
        # Create graph transformer with flexible entity extraction
        # The LLM can now propose ANY node types it finds relevant.
        # Quality control happens in the Pending-Dashboard where users review nodes.
        #
        # We use node_properties to guide the LLM without restricting it.
        graph_transformer = LLMGraphTransformer(
            llm=llm,
            # NO allowed_nodes/allowed_relationships - let the LLM be creative
            # Quality filtering happens in the review dashboard
            node_properties=["description"],  # Encourage adding descriptions
            relationship_properties=["description"],
            strict_mode=False,
        )

        # Additional guidance via the prompt (if the LLM supports system context)
        # Note: LLMGraphTransformer uses its own prompt, but we log guidance for debugging
        print("   📋 Graph extraction guidance:")
        print("      - Core entities: Organization, Person, Product, Service, Location")
        print("      - Structural entities: Process, Phase, Step, Argument, Strategy, Objection")
        print("      - Avoid generic nodes like 'Text', 'Document', 'Content'")
        
        # Process chunks in batches to avoid overwhelming the LLM
        # Take only first N chunks to avoid too many API calls
        max_chunks_for_graph = 5
        chunks_to_process = state["text_chunks"][:max_chunks_for_graph]
        
        if not chunks_to_process:
            print("   ⚠️ No chunks to process for graph extraction")
            return {
                "entities": [],
                "relationships": [],
                "status": "graph_skipped",
            }
        
        print(f"   🔍 Extracting graph from {len(chunks_to_process)} chunks using {settings.llm_model_name}...")
        
        # Convert chunks to graph documents
        graph_documents = graph_transformer.convert_to_graph_documents(chunks_to_process)
        
        # Extract entities and relationships from graph documents
        seen_entities: set = set()
        
        for graph_doc in graph_documents:
            # Process nodes
            for node in graph_doc.nodes:
                entity_key = f"{node.type}:{node.id}"
                if entity_key not in seen_entities:
                    seen_entities.add(entity_key)
                    entities.append({
                        "label": node.type,
                        "name": node.id,
                        "properties": node.properties if hasattr(node, 'properties') else {},
                    })
            
            # Process relationships
            for rel in graph_doc.relationships:
                relationships.append({
                    "from_label": rel.source.type,
                    "from_name": rel.source.id,
                    "to_label": rel.target.type,
                    "to_name": rel.target.id,
                    "type": rel.type.replace(" ", "_").upper(),
                    "properties": rel.properties if hasattr(rel, 'properties') else {},
                })
        
        # Store in Neo4j if we found entities (with PENDING status for review)
        if entities or relationships:
            graph_store = get_graph_store_service()
            result = await graph_store.add_graph_documents(
                entities=entities,
                relationships=relationships,
                document_id=state["document_id"],
                source_file=state.get("filename"),
            )
            print(f"   ✓ Graph extracted: {result['nodes_created']} nodes (PENDING), {result['relationships_created']} relationships (PENDING)")
        else:
            print("   ⚠️ No entities extracted from document")

        return {
            "entities": entities,
            "relationships": relationships,
            "status": "graph_extracted",
        }

    except ImportError as e:
        # langchain-experimental not installed
        print(f"   ⚠️ Graph extraction unavailable (missing dependency): {e}")
        return {
            "entities": [],
            "relationships": [],
            "status": "graph_skipped",
        }

    except Exception as e:
        # Graph extraction failure is NOT fatal - vectors are still indexed
        # Log warning but continue to finalize with INDEXED status
        print(f"   ⚠️ Graph extraction failed (non-fatal): {e}")
        return {
            "entities": [],
            "relationships": [],
            "status": "graph_skipped",
        }


async def finalize_node(state: IngestionState) -> dict:
    """
    Update document status in the database.
    
    Note: Graph extraction failures don't cause ERROR status.
    Only vector storage failures cause ERROR.
    """
    try:
        async with async_session_maker() as session:
            from sqlalchemy import update

            # Determine final status
            # Graph skipping is OK - we still mark as INDEXED if vectors succeeded
            if state.get("error"):
                new_status = DocumentStatus.ERROR
                error_msg = state["error"]
            else:
                new_status = DocumentStatus.INDEXED
                error_msg = None

            # Update document
            stmt = (
                update(KnowledgeDocument)
                .where(KnowledgeDocument.id == state["document_id"])
                .values(status=new_status, error_message=error_msg)
            )
            await session.execute(stmt)
            await session.commit()

        return {
            "status": new_status.value,
        }

    except Exception as e:
        print(f"Error finalizing document: {e}")
        return {
            "error": f"Failed to finalize: {str(e)}",
            "status": "error",
        }


def should_continue(state: IngestionState) -> str:
    """Determine if workflow should continue or handle error."""
    if state.get("error"):
        return "finalize"
    return "continue"


# Build the workflow graph
def create_ingestion_graph() -> StateGraph:
    """Create and compile the ingestion workflow graph."""
    
    workflow = StateGraph(IngestionState)

    # Add nodes
    workflow.add_node("load", load_node)
    workflow.add_node("split", split_node)
    workflow.add_node("vector", vector_node)
    workflow.add_node("graph", graph_node)
    workflow.add_node("finalize", finalize_node)

    # Define edges
    workflow.set_entry_point("load")
    
    workflow.add_conditional_edges(
        "load",
        should_continue,
        {"continue": "split", "finalize": "finalize"},
    )
    
    workflow.add_conditional_edges(
        "split",
        should_continue,
        {"continue": "vector", "finalize": "finalize"},
    )
    
    workflow.add_conditional_edges(
        "vector",
        should_continue,
        {"continue": "graph", "finalize": "finalize"},
    )
    
    workflow.add_edge("graph", "finalize")
    workflow.add_edge("finalize", END)

    return workflow.compile()


# Compiled graph instance
ingestion_graph = create_ingestion_graph()


async def run_ingestion_workflow(
    document_id: str,
    storage_path: str,
    filename: str,
) -> dict:
    """
    Run the ingestion workflow for a document.
    
    Args:
        document_id: UUID of the document
        storage_path: Path to the document in MinIO
        filename: Original filename
        
    Returns:
        Final workflow state
    """
    initial_state: IngestionState = {
        "document_id": document_id,
        "storage_path": storage_path,
        "filename": filename,
        "text_chunks": [],
        "entities": [],
        "relationships": [],
        "vector_ids": [],
        "error": None,
        "status": "starting",
    }

    result = await ingestion_graph.ainvoke(initial_state)
    return dict(result)
