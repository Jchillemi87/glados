import json
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END, START

# INFRASTRUCTURE & STATE
from src.core.llm import get_llm
from src.core.persistence import get_checkpointer
from src.orchestrator.state import GlobalState

# CAPABILITIES (The Sub-Agents)
# We import the pre-built graph we created in src/capabilities/research/agent.py
from src.capabilities.research.agent import research_agent

# region PROMPTS
SUPERVISOR_SYSTEM_PROMPT = """You are the Supervisor.
Your job is to route the user's request to the correct worker.

1. "research_agent": Use this for questions about:
   - Specific documents (receipts, manuals, warranties).
   - Saved personal knowledge (X570 motherboard, electric bill).
   - Any query requiring a database lookup.

2. "general_chat": Use this for:
   - Greetings ("Hello", "Hi").
   - General questions ("What is the capital of France?").
   - Questions about your identity.

Output strictly valid JSON: {"next_step": "WORKER_NAME"}
"""

# region NODES

def supervisor_node(state: GlobalState):
    """
    The Router. It does not answer the user; it only decides WHO should answer.
    """
    # We use json_mode=True to enforce strict routing logic
    llm = get_llm(temperature=0, json_mode=True)
    
    messages = [SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT)] + state['messages']
    response = llm.invoke(messages)
    
    try:
        decision = json.loads(response.content)
        next_step = decision.get("next_step", "general_chat")
    except Exception:
        # Fallback to chat if JSON fails
        next_step = "general_chat"

    # We return ONLY the routing decision, we do not append this JSON to the conversation history
    # to keep the chat log clean for the user.
    return {"next_step": next_step}


def general_chat_node(state: GlobalState):
    """
    The Generalist. Handles small talk so we don't waste expensive tool calls.
    """
    llm = get_llm(temperature=0.7)
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


# region THE GRAPH

workflow = StateGraph(GlobalState)

# Add Nodes
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("general_chat", general_chat_node)
workflow.add_node("research_agent", research_agent) # Importing the sub-graph directly!

# Define Entry Point
workflow.add_edge(START, "supervisor")

# Define Routing Logic
workflow.add_conditional_edges(
    "supervisor",
    lambda state: state["next_step"],
    {
        "research_agent": "research_agent",
        "general_chat": "general_chat"
    }
)

# Define Exit Points
# After a worker finishes, we END the turn.
# (In the future, we can route back to Supervisor for multi-step reasoning)
workflow.add_edge("general_chat", END)
workflow.add_edge("research_agent", END)

# 5. Compile
graph = workflow.compile(checkpointer=get_checkpointer())