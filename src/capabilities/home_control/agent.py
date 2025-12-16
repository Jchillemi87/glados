# src/capabilities/home_control/agent.py
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent
from src.core.llm import get_llm
from src.capabilities.home_control.tools import (
    list_available_devices, 
    control_device, 
    get_device_state
)

SYSTEM_PROMPT = """You are the Home Assistant Butler.
Your goal is to control smart devices.

### RULES
1. **Discovery First**: User input is vague. Use `list_available_devices` to find the `entity_id` (e.g. 'light.hallway_switch' or 'switch.hallway').
2. **Execute**: Once you have the ID, call `control_device`.
3. **Verify**: Report the tool's output to the user.
"""

model = get_llm(temperature=0)
tools = [list_available_devices, control_device, get_device_state]

home_agent = create_react_agent(
    model, 
    tools, 
    prompt=SystemMessage(content=SYSTEM_PROMPT)
)