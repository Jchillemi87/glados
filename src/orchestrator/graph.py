# src/orchestrator/graph.py
import json
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, END, START

from src.core.llm import get_llm
from src.core.persistence import get_checkpointer
from src.orchestrator.state import GlobalState
from src.utils.parsing import parse_json_markdown

# IMPORT AGENTS
from src.capabilities.research.agent import research_agent
from src.capabilities.home_control.agent import home_agent
from src.capabilities.system_admin.agent import system_admin_agent
from src.capabilities.finance.agent import finance_agent
from src.capabilities.scheduler.agent import scheduler_agent

# --- DYNAMIC REGISTRY ---
WORKER_REGISTRY = {
    "home_agent": {
        "description": "Controls physical smart devices (lights, switches, locks, thermostat, garage).",
        "triggers": ["turn on", "turn off", "lights", "garage", "temperature", "switch", "status"]
    },
    "research_agent": {
        "description": "Searches documents, manuals, receipts, and saved knowledge in the Vector DB.",
        "triggers": ["how do i", "warranty", "manual", "receipt", "who makes", "specs"]
    },
    "system_admin": {
        "description": "Manages server infrastructure, checks installed AI models, and monitors system status.",
        "triggers": ["list models", "what models", "ollama", "server status", "unraid"]
    },
    "finance_agent": {
        "description": "Analyzes spending history, amazon orders, and financial totals.",
        "triggers": ["how much did i spend", "price of", "amazon history", "bought", "cost"]
    },
    "scheduler_agent": {
        "description": "Handles the Morning Briefing, Calendar Events, Weather, and Maintenance Logs.",
        "triggers": ["morning briefing", "schedule", "calendar", "weather", "maintenance"]
    },
    "general_chat": {
        "description": "Handles casual conversation, jokes, greetings, and personality.",
        "triggers": ["hello", "joke", "who are you", "hi"]
    }
}

# --- TOOL MAPPING (Recovery) ---
TOOL_TO_AGENT = {
    "get_active_domains": "home_agent",
    "list_entities_in_domain": "home_agent",
    "control_device": "home_agent",
    "search_knowledge_base": "research_agent",
    "list_ollama_models": "system_admin",
    "query_amazon_orders": "finance_agent",
    "get_calendar_events": "scheduler_agent",
    "get_weather_report": "scheduler_agent",
    "log_maintenance": "scheduler_agent",
    "check_maintenance_status": "scheduler_agent"
}

def build_supervisor_prompt():
    worker_descriptions = []
    for name, info in WORKER_REGISTRY.items():
        worker_descriptions.append(f"- \"{name}\": {info['description']}")
    
    formatted_workers = "\n".join(worker_descriptions)
    
    return f"""You are the SUPERVISOR ROUTER.
Your job is to schedule the next step in the workflow.

### WORKERS
{formatted_workers}

### INSTRUCTIONS
1. Analyze the User's Request AND the Conversation History.
2. Determine if there is *unfinished work*.
   - Example: User said "Lights and Joke". History has "Lights off". -> Next: "general_chat" (for joke).
   - Example: User said "Lights and Joke". History has "Lights off" and "Joke". -> Next: "FINISH".
3. If the user's request is fully satisfied, route to "FINISH".
4. If the user's request is simple chat, route to "general_chat", then "FINISH" after that.

### OUTPUT FORMAT
Return strictly valid JSON:
{{"next_step": "WORKER_NAME"}}
or
{{"next_step": "FINISH"}}
"""

def supervisor_node(state: GlobalState):
    system_prompt = build_supervisor_prompt()
    # We use a slightly higher temperature (0.1) so it's not too rigid, but still structured
    llm = get_llm(temperature=0.1, json_mode=True)
    
    # We pass the full history so the supervisor knows what has happened
    messages = [SystemMessage(content=system_prompt)] + state['messages']
    
    try:
        response = llm.invoke(messages)
        decision = parse_json_markdown(response.content)
        next_step = decision.get("next_step")

        # --- RECOVERY LOGIC ---
        if not next_step and "name" in decision:
            tool_name = decision["name"]
            if tool_name in TOOL_TO_AGENT:
                next_step = TOOL_TO_AGENT[tool_name]
            else:
                next_step = "general_chat"

        # Validate
        valid_steps = list(WORKER_REGISTRY.keys()) + ["FINISH"]
        if next_step not in valid_steps:
            print(f"[SUPERVISOR WARNING]: Invalid route '{next_step}'. Defaulting to general_chat.")
            next_step = "general_chat"

    except Exception as e:
        print(f"[SUPERVISOR ERROR]: {e}")
        next_step = "general_chat"

    return {"next_step": next_step}

def general_chat_node(state: GlobalState):
    """
    Simple LLM response for chat/jokes.
    """
    llm = get_llm(temperature=0.7) # Creative for jokes
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

# --- GRAPH DEFINITION ---
workflow = StateGraph(GlobalState)

workflow.add_node("supervisor", supervisor_node)
workflow.add_node("general_chat", general_chat_node)
workflow.add_node("research_agent", research_agent)
workflow.add_node("home_agent", home_agent)
workflow.add_node("system_admin", system_admin_agent)
workflow.add_node("finance_agent", finance_agent)
workflow.add_node("scheduler_agent", scheduler_agent)

# Start -> Supervisor
workflow.add_edge(START, "supervisor")

# Supervisor Decision
workflow.add_conditional_edges(
    "supervisor",
    lambda state: state["next_step"],
    {
        **{key: key for key in WORKER_REGISTRY.keys()},
        "FINISH": END
    }
)

# --- CRITICAL CHANGE: THE LOOP ---
# All workers now return to the Supervisor to check for more work.
for worker in WORKER_REGISTRY.keys():
    workflow.add_edge(worker, "supervisor")

graph = workflow.compile(checkpointer=get_checkpointer())