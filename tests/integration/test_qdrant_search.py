# tests/integration/test_qdrant_search.py
import sys
import os

# --- PATH SETUP (Ensures we can import 'src') ---
# This allows running the file directly via 'python tests/...'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.core.vector import get_vector_store

def run_manual_search(query: str):
    print(f"--- Qdrant Connectivity Check ---")
    print(f"Targeting Collection: 'personal_knowledge'")
    print(f"Query: '{query}'")
    print("-" * 40)

    try:
        # Connect
        # We reuse the exact same factory function the Agent uses
        #vector_store = get_vector_store(collection_name="personal_knowledge")
        vector_store = get_vector_store(collection_name="knowledge_base")
        
        # Search
        # k=3 means "Get the top 3 matches"
        results = vector_store.similarity_search_with_score(query, k=3)

        if not results:
            print("(!) No results found. Is the collection empty?")
            return

        # Display
        for i, (doc, score) in enumerate(results, 1):
            source = doc.metadata.get("source", "Unknown")
            page = doc.metadata.get("page", "N/A")
            
            print(f"\n[Result {i}] Score: {score:.4f}")
            print(f"Source: {source} (Page {page})")
            print(f"Snippet: {doc.page_content[:200].replace('\n', ' ')}...") 
            print("-" * 20)

    except Exception as e:
        print(f"\nCRITICAL FAILURE: {e}")
        print("Check if Qdrant is running on 10.0.0.201:6333")

if __name__ == "__main__":
    # Default to "X570" if no argument provided
    search_term = sys.argv[1] if len(sys.argv) > 1 else "X570"
    run_manual_search(search_term)