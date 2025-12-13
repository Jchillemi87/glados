# src/orchestrator/state.py
import operator
from typing import Annotated, TypedDict, List
from langchain_core.messages import BaseMessage

class GlobalState(TypedDict):
    # The conversation history. 'operator.add' appends new messages rather than overwriting.
    messages: Annotated[List[BaseMessage], operator.add]
    
    # We will add 'next_step' and 'user_info' here later.
    # For a sanity check, just messages are enough.