"""
Chat API Endpoint for Agentic RAG.

Uses LangGraph workflow to orchestrate:
- Knowledge Base Search (Vector + Graph)
- SQL Query Execution
- Dynamic routing based on query intent
"""

import logging
import re
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field

from app.graph.chat_workflow import chat_workflow

router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================

class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(..., min_length=1, description="The user's message (cannot be empty)")
    history: Optional[List[ChatMessage]] = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    answer: str
    sources: List[str]
    graph_context: str
    vector_context: str


# =============================================================================
# Helper Functions
# =============================================================================

def _map_history(history_list: Optional[List[ChatMessage]]) -> List[BaseMessage]:
    """
    Maps ChatMessage list to LangChain BaseMessage list.
    
    Args:
        history_list: List of ChatMessage objects or None
        
    Returns:
        List of HumanMessage and AIMessage objects
    """
    if not history_list:
        return []
    
    messages = []
    for msg in history_list[-5:]:  # Last 5 messages for context
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))
    
    return messages


def _extract_sources_from_knowledge(knowledge_result: str) -> List[str]:
    """
    Extracts source filenames from knowledge base results.
    
    Args:
        knowledge_result: Knowledge tool output string
        
    Returns:
        List of source strings
    """
    sources = []
    
    # Pattern: [Quelle X: filename, Chunk Y]
    pattern = r'\[Quelle \d+: ([^,\]]+)(?:, Chunk (\d+))?\]'
    matches = re.findall(pattern, knowledge_result)
    
    for filename, chunk_idx in matches:
        if chunk_idx:
            sources.append(f"{filename.strip()} (Chunk {chunk_idx})")
        else:
            sources.append(filename.strip())
    
    return sources


def _extract_contexts(tool_outputs: dict) -> tuple[str, str]:
    """
    Extracts vector and graph contexts from tool outputs.
    
    Args:
        tool_outputs: Dict with tool results
        
    Returns:
        Tuple of (vector_context, graph_context)
    """
    knowledge_result = tool_outputs.get("knowledge_result", "")
    
    # Extract vector context (TEXT WISSEN section)
    vector_context = ""
    if "TEXT WISSEN" in knowledge_result:
        parts = knowledge_result.split("=== TEXT WISSEN")
        if len(parts) > 1:
            text_section = parts[1].split("===")[0]
            vector_context = text_section.strip()[:1000]  # Truncate
    
    # Extract graph context (GRAPH WISSEN section)
    graph_context = ""
    if "GRAPH WISSEN" in knowledge_result:
        parts = knowledge_result.split("=== GRAPH WISSEN")
        if len(parts) > 1:
            graph_section = parts[1].split("===")[0]
            graph_context = graph_section.strip()[:1000]  # Truncate
    
    # Fallback to SQL results if no knowledge
    if not vector_context and not graph_context:
        sql_result = tool_outputs.get("sql_result", "")
        if sql_result and "Error" not in sql_result:
            vector_context = "Datenbank-Abfrage durchgeführt"
    
    return vector_context, graph_context


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Chat with the knowledge base using Agentic RAG workflow.
    
    The LangGraph workflow will:
    1. Classify the intent (SQL vs Knowledge)
    2. Route to appropriate tools (SQL execution or Knowledge search)
    3. Generate a comprehensive answer
    """
    question = request.message.strip()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty",
        )
    
    logger.info(f"📝 Chat request: '{question[:80]}...'")
    
    try:
        # Prepare input for the workflow
        messages = _map_history(request.history)
        messages.append(HumanMessage(content=question))
        
        inputs = {
            "messages": messages,
            "intent": "general",  # Initial value, will be set by router
            "crm_target": "",  # Will be set by router if CRM entity found
            "tool_outputs": {},
        }
        
        # Execute the LangGraph workflow
        logger.info("🚀 Executing LangGraph workflow...")
        result = await chat_workflow.ainvoke(inputs)
        
        # Extract the answer (last AI message)
        if result["messages"]:
            last_message = result["messages"][-1]
            if isinstance(last_message, AIMessage):
                answer = last_message.content
            else:
                answer = "Keine Antwort erhalten."
        else:
            answer = "Keine Antwort erhalten."
        
        # Extract tool outputs
        tool_outputs = result.get("tool_outputs", {})
        
        # Extract sources from knowledge results
        knowledge_result = tool_outputs.get("knowledge_result", "")
        sources = _extract_sources_from_knowledge(knowledge_result)
        
        # Extract contexts for response
        vector_context, graph_context = _extract_contexts(tool_outputs)
        
        logger.info(f"✅ Chat completed. Answer length: {len(answer)} chars")
        
        return ChatResponse(
            answer=answer,
            sources=sources,
            graph_context=graph_context,
            vector_context=vector_context,
        )
        
    except Exception as e:
        logger.error(f"❌ Chat workflow failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat workflow failed: {str(e)}",
        )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream chat response for real-time UI updates.
    
    Returns Server-Sent Events with the response tokens.
    Uses LangGraph's astream_events to stream only the final generation.
    """
    question = request.message.strip()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty",
        )
    
    logger.info(f"📝 Stream chat request: '{question[:80]}...'")
    
    # Stream generator
    async def generate():
        try:
            # Prepare input for the workflow
            messages = _map_history(request.history)
            messages.append(HumanMessage(content=question))
            
            inputs = {
                "messages": messages,
                "intent": "general",
                "sql_context": {},
                "tool_outputs": {},
            }
            
            logger.info("🚀 Starting LangGraph streaming workflow...")
            
            # Track if we're in the generator node
            in_generator = False
            token_count = 0
            
            # Stream events from the workflow
            async for event in chat_workflow.astream_events(inputs, version="v2"):
                event_type = event.get("event")
                event_name = event.get("name", "")
                
                # Check if we entered the generator node
                if event_type == "on_chain_start" and "generator" in event_name.lower():
                    in_generator = True
                    logger.debug("📍 Entered generator node")
                
                # Check if we left the generator node
                if event_type == "on_chain_end" and "generator" in event_name.lower():
                    in_generator = False
                    logger.debug("📍 Left generator node")
                
                # Stream tokens only from the generator node's LLM
                if event_type == "on_chat_model_stream" and in_generator:
                    data = event.get("data", {})
                    chunk = data.get("chunk")
                    
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        token_count += 1
                        yield f"data: {chunk.content}\n\n"
            
            # Send completion signal
            yield "data: [DONE]\n\n"
            
            logger.info(f"✅ Streaming completed. Tokens sent: {token_count}")
            
        except Exception as e:
            logger.error(f"❌ Streaming workflow failed: {e}", exc_info=True)
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
async def knowledge_summary() -> dict:
    """
    Get a summary of the knowledge base contents.
    
    Note: This endpoint is kept for compatibility but could be enhanced
    to query the workflow state or tools directly.
    """
    # This is a simple endpoint that could be expanded
    # For now, return basic info
    return {
        "status": "ok",
        "message": "Agentic RAG workflow is active",
        "features": [
            "Knowledge Base Search (Vector + Graph)",
            "SQL Query Execution",
            "Dynamic Intent Routing",
        ],
    }
