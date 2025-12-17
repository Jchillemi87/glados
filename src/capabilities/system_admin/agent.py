from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from src.core.llm import get_llm
from src.core.middleware import ToolEnforcementMiddleware
from src.capabilities.system_admin.tools import list_ollama_models

SYSTEM_PROMPT = """You are the System Administrator for the Unraid Server.
Your job is to manage server resources and inspect system state.

### PROTOCOL
1. **Accuracy**: Report technical details exactly as returned by tools.
2. **Safety**: Do not hallucinate metrics or configurations.
3. **Action**: If asked to list things, call the appropriate list tool immediately.
"""

model = get_llm(temperature=0)
tools = [list_ollama_models]

system_admin_agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=SystemMessage(content=SYSTEM_PROMPT),
    middleware=[ToolEnforcementMiddleware(strict_mode=True)]
)