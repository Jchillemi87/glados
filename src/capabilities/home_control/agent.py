from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from src.core.llm import get_llm
from src.core.middleware import ToolEnforcementMiddleware
from src.capabilities.home_control.tools import (
    list_available_devices, 
    control_device, 
    get_device_state
)

# ROBOTIC PROMPT
# We remove "Butler" persona to reduce "Chatty" tendency.
SYSTEM_PROMPT = """You are a Home Automation API Wrapper.
Your ONLY function is to translate user intent into Tool Calls.

### INCORRECT BEHAVIOR
User: "Turn on the kitchen light."
You: "I have turned on the kitchen light."  <-- WRONG! No tool was called.

### CORRECT BEHAVIOR
User: "Turn on the kitchen light."
You: (Call Tool: list_available_devices)
...
You: (Call Tool: control_device)
...
You: "SUCCESS: Light is on."

### PROTOCOL
1. ALWAYS call `list_available_devices` first.
2. NEVER guess an ID.
3. NEVER output text describing an action unless the tool has already returned "SUCCESS".
"""

# Increase temperature slightly to allow it to "think" about the example, 
# but keep it low for precision.
model = get_llm(temperature=0.1)

tools = [list_available_devices, control_device, get_device_state]

# We attach the middleware to catch any slips
home_agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=SystemMessage(content=SYSTEM_PROMPT),
    middleware=[ToolEnforcementMiddleware(strict_mode=True)]
)