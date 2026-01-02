"""
Vector Store Service using PGVector for document embeddings.

Stores document chunks with their embeddings in PostgreSQL using pgvector.
Supports OpenAI-compatible embedding APIs (e.g., Trooper/Jina).
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import List, Tuple

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector

from app.core.config import VECTOR_COLLECTION_NAME, get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Thread pool for running blocking operations
_executor = ThreadPoolExecutor(max_workers=2)


class VectorStoreService:
    """
    Service for storing and retrieving document embeddings using PGVector.
    
    Uses configurable OpenAI-compatible embedding API (Trooper/Jina/OpenAI).
    """

    def __init__(self):
        """Initialize the vector store with configured embeddings."""
        if not settings.embedding_api_key:
            raise ValueError("EMBEDDING_API_KEY is required for vector store")

        # Initialize embeddings with OpenAI-compatible API
        self.embeddings = OpenAIEmbeddings(
            openai_api_base=settings.embedding_api_url,
            openai_api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            check_embedding_ctx_length=False,  # Required for non-OpenAI models
        )

        # Build connection string for PGVector (sync driver)
        connection_string = (
            f"postgresql+psycopg://{settings.postgres_user}:{settings.postgres_password}"
            f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
        )

        # IMPORTANT: Use consistent collection_name for both read and write
        self.vector_store = PGVector(
            embeddings=self.embeddings,
            collection_name=VECTOR_COLLECTION_NAME,
            connection=connection_string,
            use_jsonb=True,
        )

        logger.info(f"VectorStoreService initialized with collection: {VECTOR_COLLECTION_NAME}")

    async def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous function in the thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, partial(func, *args, **kwargs)
        )

    async def add_documents(
        self,
        chunks: List[Document],
        document_id: str,
    ) -> List[str]:
        """
        Add document chunks to the vector store.
        
        Args:
            chunks: List of LangChain Document objects with page_content and metadata
            document_id: The parent document ID for reference
            
        Returns:
            List of chunk IDs
        """
        # Add document_id to metadata of each chunk
        for chunk in chunks:
            chunk.metadata["document_id"] = document_id

        # Run the blocking operation in thread pool
        ids = await self._run_sync(
            self.vector_store.add_documents,
            chunks,
        )
        
        return ids

    async def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter_dict: dict | None = None,
        score_threshold: float | None = 0.5,
    ) -> List[Document]:
        """
        Search for similar documents with score filtering.
        
        Args:
            query: Search query string
            k: Number of results to return
            filter_dict: Optional metadata filter
            score_threshold: Maximum distance score (lower is better for cosine distance).
                           Set to None to disable filtering.
            
        Returns:
            List of matching Document objects (filtered by score if threshold is set)
        """
        # Use similarity_search_with_score to get distances
        results_with_scores: List[Tuple[Document, float]] = await self._run_sync(
            self.vector_store.similarity_search_with_score,
            query,
            k=k,
            filter=filter_dict,
        )
        
        logger.info(f"Vector search for '{query[:50]}...' returned {len(results_with_scores)} results")
        
        # Log all scores for debugging
        for doc, score in results_with_scores:
            filename = doc.metadata.get("filename", "Unknown")
            logger.debug(f"  - {filename}: score={score:.4f}")
        
        # Filter by score threshold if specified
        if score_threshold is not None:
            filtered_results = []
            for doc, score in results_with_scores:
                if score <= score_threshold:
                    filtered_results.append(doc)
                else:
                    filename = doc.metadata.get("filename", "Unknown")
                    logger.warning(f"  ⚠️ Filtered out '{filename}' due to poor score: {score:.4f} > {score_threshold}")
            
            logger.info(f"After score filtering: {len(filtered_results)} results (threshold={score_threshold})")
            return filtered_results
        
        # Return all results without filtering
        return [doc for doc, _ in results_with_scores]

    async def delete_by_document_id(self, document_id: str) -> None:
        """
        Delete all chunks for a specific document.

        Args:
            document_id: The document ID to delete chunks for
        """
        # Use filter to find and delete
        await self._run_sync(
            self.vector_store.delete,
            filter={"document_id": document_id},
        )

    async def delete_by_filename(self, filename: str) -> int:
        """
        Delete all chunks for a specific filename.

        Args:
            filename: The filename to delete chunks for

        Returns:
            Number of deleted chunks (approximate)
        """
        logger.info(f"Deleting vectors for filename: {filename}")

        # Use filter to find and delete by filename in metadata
        try:
            await self._run_sync(
                self.vector_store.delete,
                filter={"filename": filename},
            )
            logger.info(f"Deleted vectors for filename: {filename}")
            return 1  # PGVector doesn't return count, return 1 on success
        except Exception as e:
            logger.error(f"Failed to delete vectors for {filename}: {e}")
            raise


# Singleton instance
_vector_store_service: VectorStoreService | None = None


def get_vector_store_service() -> VectorStoreService:
    """Get or create vector store service singleton."""
    global _vector_store_service
    if _vector_store_service is None:
        _vector_store_service = VectorStoreService()
    return _vector_store_service
