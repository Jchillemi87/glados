from langchain.agents import create_agent
from langchain.messages import SystemMessage
from src.core.llm import get_llm
from src.core.middleware import ToolEnforcementMiddleware
from src.capabilities.research.tools import search_knowledge_base

SYSTEM_PROMPT = """You are the Research Specialist.
Your job is to find information in the Knowledge Base.
Always search before answering. Quote the document source if available.
"""

model = get_llm(temperature=0)
tools = [search_knowledge_base]

research_agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=SystemMessage(content=SYSTEM_PROMPT),
    middleware=[ToolEnforcementMiddleware(strict_mode=True)]
)