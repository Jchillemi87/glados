# src/core/vector.py
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
from src.core.config import settings
from src.core.llm import get_embeddings

def get_qdrant_client() -> QdrantClient:
    """
    Returns the raw Qdrant client.
    Used for administrative tasks: creating collections, deleting data, checking health.
    """
    return QdrantClient(
        url=settings.QDRANT_URL,  # Loaded from .env (http://10.0.0.201:6333)
        timeout=60,               # Increased timeout to prevent crashes on large queries
        prefer_grpc=False         # Force HTTP for stability on local Docker networks
    )

def get_vector_store(collection_name: str = "personal_knowledge") -> QdrantVectorStore:
    """
    Returns the LangChain Vector Store wrapper.
    Used by the Agent to search for documents.
    
    Args:
        collection_name: Separate 'finance' from 'manuals' if needed.
    """
    client = get_qdrant_client()
    embeddings = get_embeddings()

    # We return an initialized store ready for searching
    return QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
    )