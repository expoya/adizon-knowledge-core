"""
Knowledge Base Tool für LangGraph Agents.
Kapselt die Hybrid RAG Suche (Vector + Graph).
"""

import logging
from typing import Annotated

from langchain_core.tools import tool

from app.core.config import VECTOR_COLLECTION_NAME
from app.prompts import get_prompt
from app.services.graph_store import GraphStoreService, get_graph_store_service
from app.services.vector_store import VectorStoreService, get_vector_store_service

logger = logging.getLogger(__name__)

# Load tool description from prompts folder
_TOOL_DESCRIPTION = get_prompt("tool_search_knowledge_base")


@tool
async def search_knowledge_base(query: str) -> str:
    """Durchsucht die interne Wissensdatenbank (Vector Store + Knowledge Graph) nach relevanten Informationen.
    
    Diese Funktion führt eine hybride Suche durch:
    1. Vector Search: Findet semantisch ähnliche Dokument-Abschnitte
    2. Graph Query: Findet relevante Entities und deren Beziehungen
    
    Args:
        query: Die Suchanfrage oder Frage
        
    Returns:
        Kombinierte Ergebnisse aus Vector Store und Knowledge Graph
    """
    
    logger.info(f"🔧 Knowledge Tool: Searching for '{query[:80]}...'")
    
    # Initialisiere Services
    vector_store = get_vector_store_service()
    graph_store = get_graph_store_service()
    
    result_parts = []
    
    # Teil 1: Vector Search für Textabschnitte
    try:
        logger.debug(f"🔍 Vector search in collection: {VECTOR_COLLECTION_NAME}")
        vector_results = await vector_store.similarity_search(
            query=query,
            k=5,
            score_threshold=0.8,
        )
        
        if vector_results:
            result_parts.append("=== TEXT WISSEN (Relevante Dokument-Abschnitte) ===\n")
            
            for i, doc in enumerate(vector_results):
                filename = doc.metadata.get("filename", "Unknown")
                chunk_idx = doc.metadata.get("chunk_index", 0)
                content = doc.page_content[:500]  # Limit content length
                
                result_parts.append(
                    f"[Quelle {i+1}: {filename}, Chunk {chunk_idx}]\n{content}\n"
                )
            
            logger.info(f"✅ Vector search: {len(vector_results)} chunks found")
        else:
            result_parts.append("=== TEXT WISSEN ===\nKeine relevanten Textabschnitte gefunden.\n")
            logger.info("⚠️ Vector search: No results found")
            
    except Exception as e:
        logger.error(f"❌ Vector search failed: {e}", exc_info=True)
        result_parts.append("=== TEXT WISSEN ===\nVektor-Suche nicht verfügbar.\n")
    
    # Teil 2: Graph Search für Entitäten und Beziehungen
    try:
        logger.debug("🕸️ Querying graph database")
        context_graph = await graph_store.query_graph(query)
        
        if context_graph and context_graph.strip():
            result_parts.append("\n=== GRAPH WISSEN (Entitäten und Beziehungen) ===\n")
            result_parts.append(context_graph)
            
            graph_lines = len(context_graph.strip().split('\n'))
            logger.info(f"✅ Graph search: {graph_lines} relationships found")
        else:
            result_parts.append("\n=== GRAPH WISSEN ===\nKeine Graph-Daten verfügbar.\n")
            logger.info("⚠️ Graph search: No results found")
            
    except Exception as e:
        logger.error(f"❌ Graph search failed: {e}", exc_info=True)
        result_parts.append("\n=== GRAPH WISSEN ===\nGraph-Suche nicht verfügbar.\n")
    
    # Kombiniere alle Teile
    final_result = "".join(result_parts)
    
    logger.info(f"✅ Knowledge Tool: Returned {len(final_result)} chars of context")
    
    return final_result


# Set docstring after function definition
search_knowledge_base.__doc__ = _TOOL_DESCRIPTION
