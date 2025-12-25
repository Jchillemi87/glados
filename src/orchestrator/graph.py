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
        "description": "Controls physical smart devices (lights, switches, locks, thermostat).",
        "triggers": ["turn on", "turn off", "lights", "garage", "temperature", "switch", "status"]
    },
    "research_agent": {
        "description": "Searches documents, manuals, receipts, and saved knowledge.",
        "triggers": ["how do i", "warranty", "manual", "receipt", "who makes", "specs", "tire pressure", "motherboard"]
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
        "description": "Handles the Morning Briefing, Calendar Events, Weather, and Maintenance Logs (Oil changes, Filters).",
        "triggers": ["morning briefing", "what is on my schedule", "calendar", "weather", "maintenance", "oil change", "filter"]
    },
    "general_chat": {
        "description": "Handles greetings, identity questions, and casual conversation.",
        "triggers": ["hello", "hi", "who are you", "joke"]
    }
}

# --- GUARDRAILS: TOOL MAPPING ---
TOOL_TO_AGENT = {
    # Home Control
    "list_available_devices": "home_agent",
    "control_device": "home_agent",

    # Research
    "search_knowledge_base": "research_agent",

    # System Admin
    "list_ollama_models": "system_admin",

    # Finance
    "query_amazon_orders": "finance_agent",

    # Scheduler
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
Your ONLY job is to route the user request to the correct worker.
You CANNOT answer questions directly. You CANNOT execute tools.

### WORKERS
{formatted_workers}

### OUTPUT FORMAT
Return strictly valid JSON:
{{"next_step": "WORKER_NAME"}}
"""

def supervisor_node(state: GlobalState):
    system_prompt = build_supervisor_prompt()
    llm = get_llm(temperature=0, json_mode=True)
    
    messages = [SystemMessage(content=system_prompt)] + state['messages']
    response = llm.invoke(messages)
    
    print(f"\n[SUPERVISOR THOUGHT]: {response.content}")

    try:
        decision = parse_json_markdown(response.content)
        next_step = decision.get("next_step")

        if not next_step and "name" in decision:
            tool_name = decision["name"]
            print(f"[SUPERVISOR WARNING]: Model tried to call tool '{tool_name}'.")
            
            if tool_name in TOOL_TO_AGENT:
                next_step = TOOL_TO_AGENT[tool_name]
                print(f"[SUPERVISOR RECOVERY]: Redirecting to owner -> {next_step}")
            else:
                next_step = "general_chat"

        if next_step not in WORKER_REGISTRY:
            next_step = "general_chat"

    except Exception as e:
        print(f"[SUPERVISOR ERROR]: JSON parsing failed ({e}). Defaulting to Chat.")
        next_step = "general_chat"

    print(f"[SUPERVISOR ROUTE]: -> {next_step}")
    return {"next_step": next_step}

def general_chat_node(state: GlobalState):
    print("[NODE]: General Chat")
    llm = get_llm(temperature=0.7)
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

# --- GRAPH ---
workflow = StateGraph(GlobalState)

workflow.add_node("supervisor", supervisor_node)
workflow.add_node("general_chat", general_chat_node)
workflow.add_node("research_agent", research_agent)
workflow.add_node("home_agent", home_agent)
workflow.add_node("system_admin", system_admin_agent)
workflow.add_node("finance_agent", finance_agent)
workflow.add_node("scheduler_agent", scheduler_agent)

workflow.add_edge(START, "supervisor")

workflow.add_conditional_edges(
    "supervisor",
    lambda state: state["next_step"],
    {key: key for key in WORKER_REGISTRY.keys()}
)

for worker in WORKER_REGISTRY.keys():
    if worker != "supervisor":
        workflow.add_edge(worker, END)

graph = workflow.compile(checkpointer=get_checkpointer())