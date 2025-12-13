# src/orchestrator/state.py

import operator
from typing import Annotated, TypedDict, List, Literal
from langchain_core.messages import BaseMessage

class GlobalState(TypedDict):
    # HISTORY: Holds the entire conversation
    messages: Annotated[List[BaseMessage], operator.add]
    
    # ROUTING: The Supervisor writes to this (e.g., "research_agent")
    next_step: str
    
    # CONTEXT: Tracks which agent sent the last message
    # Useful for the UI to know if "Finance" or "Research" is speaking
    sender: str