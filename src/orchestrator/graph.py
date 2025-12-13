# src/orchestrator/graph.py
from langgraph.graph import StateGraph, START, END
from src.core.llm import get_llm
from src.core.persistence import get_checkpointer
from src.orchestrator.state import GlobalState

# THE SIMPLE NODE
# a simple chatbot
def chatbot_node(state: GlobalState):
    llm = get_llm(temperature=0.7) # 0.7 for a natural conversation (not robotic)

    response = llm.invoke(state["messages"]) # The LLM reads the history and generates a response

    return {"messages": [response]} # We return the new message to append it to history

# THE GRAPH
workflow = StateGraph(GlobalState)

# Add the single node
workflow.add_node("chatbot", chatbot_node)

# Create a straight line: START -> CHATBOT -> END
workflow.add_edge(START, "chatbot")
workflow.add_edge("chatbot", END)

# THE COMPILATION (CRITICAL)
# You MUST pass the checkpointer here, or the bot will have amnesia.
graph = workflow.compile(checkpointer=get_checkpointer())