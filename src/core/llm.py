# src/core/llm.py
from langchain_ollama import ChatOllama, OllamaEmbeddings
from src.core.config import settings

def get_llm(temperature: float = 0, json_mode: bool = False) -> ChatOllama:
    """
    Returns the configured Chat Model (The Brain).
    
    Args:
        temperature: 0 for factual/math (Admin), 0.7 for creative (Writing).
        json_mode: If True, enforces valid JSON output (critical for Tools).
    """
    return ChatOllama(
        model=settings.DEFAULT_MODEL,        # Loaded from .env (e.g., "llama3.2:latest")
        base_url=settings.OLLAMA_BASE_URL,   # Loaded from .env (e.g., "http://10.0.0.201:11434")
        temperature=temperature,
        format="json" if json_mode else "",  # Enforces structured output if requested
        # Keep-alive ensures the model stays in VRAM for faster subsequent responses
        keep_alive="5m"  
    )

def get_embeddings() -> OllamaEmbeddings:
    """
    Returns the configured Embedding Model (The Translator).
    Used by the Vector Store to turn text into numbers.
    """
    return OllamaEmbeddings(
        model=settings.EMBEDDING_MODEL,      # Loaded from .env (e.g., "nomic-embed-text")
        base_url=settings.OLLAMA_BASE_URL,
    )