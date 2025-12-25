# src/capabilities/home_control/agent.py
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from src.core.llm import get_llm
from src.core.middleware import ToolEnforcementMiddleware
from src.capabilities.home_control.tools import (
    list_available_devices, 
    control_device
)

# STRICT PROCEDURAL PROMPT
SYSTEM_PROMPT = """You are the Home Assistant Butler.

### PRIME DIRECTIVE: NO BLIND ACTIONS
You are BLIND. You CANNOT see device IDs.
You MUST follow this 2-Step Protocol for EVERY request:

**STEP 1: DISCOVERY**
- Call `list_available_devices(domain_filter='keyword')`.
- If the output contains the specific details you need, proceed.
- If the output lists multiple devices, pick the correct ID.

**STEP 2: ACTION**
- Call `control_device`.
- If dimming, use `brightness_pct` (0-100).

### EXAMPLES
User: "Dim kitchen to 50%"
1. `list_available_devices(domain_filter='kitchen')`
2. Found `light.kitchen_main`.
3. `control_device(service='turn_on', entity_id='light.kitchen_main', brightness_pct=50)`
"""

model = get_llm(temperature=0)

# We removed get_device_state to force usage of the Smart List
tools = [list_available_devices, control_device]

home_agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=SystemMessage(content=SYSTEM_PROMPT),
    middleware=[ToolEnforcementMiddleware(strict_mode=True)]
)