# src/capabilities/research/tools.py
from langchain_core.tools import tool
from src.core.vector import get_vector_store

@tool
def search_knowledge_base(query: str) -> str:
    """
    USE THIS TOOL to search for specific documents, manuals, receipts, or files.
    Input should be a targeted keyword search (e.g., "warranty blender", "electric bill january").
    Do not use full sentences.
    """
    try:
        # Connect to the 'personal_knowledge' collection
        vector_store = get_vector_store(collection_name="personal_knowledge")
        # vector_store = get_vector_store(collection_name="knowledge_base")
        
        # Search for top 5 chunks (Increased from 3 for better context)
        results = vector_store.similarity_search(query, k=5)
        
        if not results:
            return "No relevant documents found in the knowledge base."
            
        # Format the results strictly for the LLM to read
        formatted_results = "\n\n".join(
            f"--- Document: {doc.metadata.get('title', 'Untitled')} ---\n"
            f"Source: {doc.metadata.get('source', 'Unknown')}\n"
            f"Content: {doc.page_content}"
            for doc in results
        )
        return formatted_results

    except Exception as e:
        return f"Error searching knowledge base: {e}"