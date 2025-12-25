# src/core/persistence.py
from langgraph.checkpoint.memory import MemorySaver

def get_checkpointer():
    """
    Returns an In-Memory checkpointer.
    
    PROS:
    - Fast
    - No database locks
    - Works with Async (Chainlit) and Sync (CLI)
    
    CONS:
    - History is lost when the script stops.
    """
    return MemorySaver()