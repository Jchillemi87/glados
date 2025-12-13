from langchain_core.tools import tool
from src.core.vector import get_qdrant_client

@tool
def search_personal_knowledge(query: str):
    """Searches for details about hardware, pets, etc."""
    # Logic adapted from 'retriever' lines 55-64
    client = get_qdrant_client()