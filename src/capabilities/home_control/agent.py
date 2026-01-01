# %% src/capabilities/home_control/agent.py
import json
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from src.core.llm import get_llm
from src.core.middleware import ToolEnforcementMiddleware
from src.orchestrator.state import GlobalState
from src.capabilities.home_control.tools import (
    get_active_domains,
    list_entities_in_domain, 
    control_device
)

# --- NODE 1: DOMAIN SCANNER ---
def domain_scanner_node(state: GlobalState):
    try:
        # We don't print here to keep the UI clean (the tool call shows up anyway)
        msg = SystemMessage(
            content="## PHASE 1: DISCOVERY\nI have injected the `get_active_domains` tool result below. Use it to orient yourself."
        )
        # We manually invoke to ensure the context is loaded immediately for the LLM
        domains = get_active_domains.invoke({})
        tool_msg = SystemMessage(content=f"## SYSTEM: ACTIVE DOMAINS\n{domains}")
        return {"messages": [msg, tool_msg]}
    except Exception as e:
        return {"messages": [SystemMessage(content=f"Error scanning domains: {e}")]}

# --- NODE 2: DRILL DOWN (Logic Engine) ---
def drill_down_node(state: GlobalState):
    model = get_llm(temperature=0)
    tools = [list_entities_in_domain] 
    model = model.bind_tools(tools)
    
    prompt = """You are the Home Assistant Scout.

    ### YOUR GOAL
    Identify **physical devices** that need to be controlled based on the user's request.
    
    ### RULES
    1. **IGNORE Conversational Requests:** - If user says "Turn off lights and tell me a joke", ONLY focus on "Turn off lights".
       - IGNORE "tell me a joke", "who are you".
       - The Supervisor will handle those other parts later.
    2. **Look for Domains:**
       - "Lights" -> `light`
       - "Thermostat" -> `climate`
       - "Front Door" -> `lock`, `binary_sensor`
       - "Printer" -> `sensor`
    3. **Action:**
       - Call `list_entities_in_domain(domain=...)` for the relevant domain.
    
    If the user's request is purely conversational (e.g., "Tell me a joke") and has NO device control, do not call any tools. Just output "PASS".
    """
    
    chain = ChatPromptTemplate.from_messages([
        ("system", prompt),
        MessagesPlaceholder(variable_name="messages"),
    ]) | model
    
    response = chain.invoke(state)
    return {"messages": [response]}

# --- NODE 3: FALLBACK ---
def hard_fallback_scan_node(state: GlobalState):
    print("[HomeAgent] LLM stalled. Executing HARD FALLBACK scan.")
    try:
        lights = list_entities_in_domain.invoke({"domain": "light"})
        switches = list_entities_in_domain.invoke({"domain": "switch"})
        
        # Merge lists
        l = json.loads(lights)
        s = json.loads(switches)
        combined = json.dumps(l + s, indent=2)
        
        msg = SystemMessage(content=f"## SYSTEM FALLBACK: LIGHTS & SWITCHES\n{combined}")
        return {"messages": [msg]}
    except:
        return {"messages": [SystemMessage(content="## SYSTEM FALLBACK FAILED")]}

# --- NODE 4: EXECUTOR (Anti-Hallucination) ---
def executor_node(state: GlobalState):
    model = get_llm(temperature=0)
    tools = [control_device]
    model = model.bind_tools(tools)
    
    prompt = """You are the Home Assistant Operator.

    ### INSTRUCTIONS
    1. Review the **Lists of Entities** provided in the history.
    2. Match the user's request to a specific `entity_id`.
    3. Execute `control_device`.

    ### CRITICAL SECURITY RULES
    1. **NO GUESSING:** You MUST see the `entity_id` in the provided JSON lists before using it.
    2. **NO INVENTING:** Do not make up IDs like `tts.google_say` or `light.kitchen_screen`. 
    3. **IF NOT FOUND:** If the device is not in the list, say "I could not find a device named X in the [domain] domain."
    
    ### FORMAT
    Call the tool `control_device` with arguments:
    - `entity_id`: The exact ID found.
    - `service`: 'turn_on', 'turn_off', etc.
    - `parameters`: Dictionary (e.g. {{ "brightness_pct": 50 }}).
    """
    
    chain = ChatPromptTemplate.from_messages([
        ("system", prompt),
        MessagesPlaceholder(variable_name="messages"),
    ]) | model
    
    middleware = ToolEnforcementMiddleware(strict_mode=True)
    modified_state = middleware.before_model(state)
    response = chain.invoke(modified_state)
    final_response = middleware.after_model(response)
    
    return {"messages": [final_response]}

# --- GRAPH ---
workflow = StateGraph(GlobalState)

workflow.add_node("scanner", domain_scanner_node)
workflow.add_node("drill_down", drill_down_node)
workflow.add_node("list_tool", ToolNode([list_entities_in_domain]))
workflow.add_node("fallback", hard_fallback_scan_node)
workflow.add_node("executor", executor_node)
workflow.add_node("control_tool", ToolNode([control_device]))

workflow.add_edge(START, "scanner")
workflow.add_edge("scanner", "drill_down")

def route_drill_down(state: GlobalState):
    last_msg = state["messages"][-1]
    
    # If tool called, proceed
    if last_msg.tool_calls:
        return "list_tool"
    
    # If the model said "PASS" (pure conversation), we end early.
    if "PASS" in last_msg.content:
        return END
        
    # If ambiguous/failed, force scan
    return "fallback"

workflow.add_conditional_edges("drill_down", route_drill_down, ["list_tool", "fallback", END])

workflow.add_edge("list_tool", "executor")
workflow.add_edge("fallback", "executor")

def route_executor(state: GlobalState):
    last_msg = state["messages"][-1]
    if last_msg.tool_calls:
        return "control_tool"
    return END

workflow.add_conditional_edges("executor", route_executor, ["control_tool", END])
workflow.add_edge("control_tool", END)

home_agent = workflow.compile()