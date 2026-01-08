"""
LLM Factory für die Anwendung.
Zentrale Stelle zum Erstellen von LLM-Instanzen.
"""

from langchain_openai import ChatOpenAI

from app.core.config import get_settings

settings = get_settings()


def get_llm(temperature: float = 0.7, streaming: bool = True) -> ChatOpenAI:
    """
    Get the configured LLM for chat.
    Uses the Trooper server with the configured model.
    
    Args:
        temperature: Temperature for the LLM (0.0 = deterministic, 1.0 = creative)
        streaming: Whether to enable streaming responses
        
    Returns:
        Configured ChatOpenAI instance
    """
    return ChatOpenAI(
        openai_api_base=settings.embedding_api_url,
        openai_api_key=settings.embedding_api_key,
        model_name=settings.llm_model_name,
        temperature=temperature,
        streaming=streaming,
    )

