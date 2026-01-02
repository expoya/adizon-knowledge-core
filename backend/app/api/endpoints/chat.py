"""
Chat API Endpoint for Hybrid RAG.

Combines vector search (PGVector) and graph search (Neo4j)
to answer questions using the knowledge base.
"""

import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.config import VECTOR_COLLECTION_NAME, get_settings
from app.services.graph_store import GraphStoreService, get_graph_store_service
from app.services.vector_store import VectorStoreService, get_vector_store_service

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str
    history: Optional[List[ChatMessage]] = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    answer: str
    sources: List[str]
    graph_context: str
    vector_context: str


class SourceInfo(BaseModel):
    """Information about a source document."""
    filename: str
    chunk_index: int
    content_preview: str


def get_llm() -> ChatOpenAI:
    """
    Get the configured LLM for chat.
    Uses the Trooper server with the configured model.
    """
    return ChatOpenAI(
        openai_api_base=settings.embedding_api_url,
        openai_api_key=settings.embedding_api_key,
        model_name=settings.llm_model_name,
        temperature=0.7,
        streaming=True,
    )


SYSTEM_PROMPT = """Du bist ein hilfreicher Assistent für Adizon Knowledge Core.
Deine Aufgabe ist es, Fragen basierend auf den bereitgestellten Informationen zu beantworten.

Beachte:
- Nutze NUR die bereitgestellten Informationen für deine Antwort
- Wenn die Informationen nicht ausreichen, sage das ehrlich
- Antworte präzise und strukturiert
- Zitiere relevante Fakten aus dem Kontext
- Antworte auf Deutsch, es sei denn, die Frage ist auf Englisch

GRAPH WISSEN (Entitäten und Beziehungen):
{context_graph}

TEXT WISSEN (Relevante Dokument-Abschnitte):
{context_text}
"""


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    vector_store: Annotated[VectorStoreService, Depends(get_vector_store_service)],
    graph_store: Annotated[GraphStoreService, Depends(get_graph_store_service)],
) -> ChatResponse:
    """
    Chat with the knowledge base using Hybrid RAG.
    
    Process:
    1. Search vectors (Jina embeddings) for relevant text chunks
    2. Query graph (Neo4j) for relevant entities and relationships
    3. Combine context and send to LLM (Trooper/Ministral)
    4. Return answer with sources
    """
    question = request.message.strip()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty",
        )

    logger.info(f"📝 Chat request: '{question[:80]}...'")

    # Step 1: Vector search
    try:
        print(f"🔍 Searching in collection: {VECTOR_COLLECTION_NAME} with query: {question[:50]}...")
        vector_results = await vector_store.similarity_search(
            query=question,
            k=5,
            score_threshold=0.8,  # Allow slightly higher scores for broader matches
        )
        print(f"✅ Found {len(vector_results)} chunks via vector search")
        
        # Format vector context
        context_text_parts = []
        sources = []
        for i, doc in enumerate(vector_results):
            filename = doc.metadata.get("filename", "Unknown")
            chunk_idx = doc.metadata.get("chunk_index", 0)
            content = doc.page_content[:500]  # Limit content length
            
            context_text_parts.append(f"[Quelle {i+1}: {filename}]\n{content}")
            sources.append(f"{filename} (Chunk {chunk_idx})")
        
        context_text = "\n\n".join(context_text_parts) if context_text_parts else "Keine relevanten Textabschnitte gefunden."
        
        logger.info(f"🔍 Vector search: {len(vector_results)} chunks found")
        
    except Exception as e:
        logger.error(f"Vector search failed: {e}", exc_info=True)
        context_text = "Vektor-Suche nicht verfügbar."
        sources = []

    # Step 2: Graph search
    try:
        context_graph = await graph_store.query_graph(question)
        if not context_graph:
            context_graph = "Keine Graph-Daten verfügbar."
            logger.info("🕸️ Graph search: No results found")
        else:
            graph_lines = len(context_graph.strip().split('\n'))
            logger.info(f"🕸️ Graph search: {graph_lines} relationships found")
    except Exception as e:
        logger.error(f"Graph search failed: {e}", exc_info=True)
        context_graph = "Graph-Suche nicht verfügbar."

    # Log context summary before LLM call
    logger.info(f"🤖 Calling LLM with context: {len(context_text)} chars text, {len(context_graph)} chars graph")

    # Step 3: Build prompt and call LLM
    try:
        llm = get_llm()
        
        # Build the system prompt with context
        system_content = SYSTEM_PROMPT.format(
            context_graph=context_graph,
            context_text=context_text,
        )
        
        # Build message history
        messages = [SystemMessage(content=system_content)]
        
        # Add conversation history if provided
        if request.history:
            for msg in request.history[-5:]:  # Last 5 messages for context
                if msg.role == "user":
                    messages.append(HumanMessage(content=msg.content))
                # Skip assistant messages for now - could add AIMessage later
        
        # Add current question
        messages.append(HumanMessage(content=question))
        
        # Get response from LLM
        response = await llm.ainvoke(messages)
        answer = response.content
        
    except Exception as e:
        print(f"LLM call failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM call failed: {str(e)}",
        )

    return ChatResponse(
        answer=answer,
        sources=sources,
        graph_context=context_graph,
        vector_context=context_text[:1000],  # Truncate for response
    )


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    vector_store: Annotated[VectorStoreService, Depends(get_vector_store_service)],
    graph_store: Annotated[GraphStoreService, Depends(get_graph_store_service)],
):
    """
    Stream chat response for real-time UI updates.
    
    Returns Server-Sent Events with the response tokens.
    """
    question = request.message.strip()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty",
        )

    logger.info(f"📝 Stream chat request: '{question[:80]}...'")

    # Get context (same as non-streaming)
    try:
        print(f"🔍 [Stream] Searching in collection: {VECTOR_COLLECTION_NAME} with query: {question[:50]}...")
        vector_results = await vector_store.similarity_search(query=question, k=5, score_threshold=0.8)
        print(f"✅ [Stream] Found {len(vector_results)} chunks via vector search")
        context_text_parts = []
        for i, doc in enumerate(vector_results):
            filename = doc.metadata.get("filename", "Unknown")
            content = doc.page_content[:500]
            context_text_parts.append(f"[Quelle {i+1}: {filename}]\n{content}")
        context_text = "\n\n".join(context_text_parts) if context_text_parts else "Keine relevanten Textabschnitte gefunden."
        logger.info(f"🔍 Vector search (stream): {len(vector_results)} chunks found")
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        context_text = "Vektor-Suche nicht verfügbar."

    try:
        context_graph = await graph_store.query_graph(question)
        if not context_graph:
            context_graph = "Keine Graph-Daten verfügbar."
            logger.info("🕸️ Graph search (stream): No results found")
        else:
            logger.info(f"🕸️ Graph search (stream): {len(context_graph.strip().split(chr(10)))} relationships found")
    except Exception as e:
        logger.error(f"Graph search failed: {e}")
        context_graph = "Graph-Suche nicht verfügbar."
    
    logger.info(f"🤖 Calling LLM (stream) with context: {len(context_text)} chars text, {len(context_graph)} chars graph")

    # Stream generator
    async def generate():
        try:
            llm = get_llm()
            
            system_content = SYSTEM_PROMPT.format(
                context_graph=context_graph,
                context_text=context_text,
            )
            
            messages = [
                SystemMessage(content=system_content),
                HumanMessage(content=question),
            ]
            
            async for chunk in llm.astream(messages):
                if chunk.content:
                    yield f"data: {chunk.content}\n\n"
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/knowledge/summary")
async def knowledge_summary(
    vector_store: Annotated[VectorStoreService, Depends(get_vector_store_service)],
    graph_store: Annotated[GraphStoreService, Depends(get_graph_store_service)],
) -> dict:
    """
    Get a summary of the knowledge base contents.
    """
    try:
        graph_summary = await graph_store.get_graph_summary()
    except Exception as e:
        graph_summary = f"Graph nicht verfügbar: {e}"

    return {
        "graph": graph_summary,
        "status": "ok",
    }

