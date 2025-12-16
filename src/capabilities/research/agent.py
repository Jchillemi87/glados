# src/capabilities/research/agent.py
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent
from src.core.llm import get_llm
from src.capabilities.research.tools import search_knowledge_base

SYSTEM_PROMPT = """You are the Research Specialist.
Your ONLY job is to query the 'search_knowledge_base' tool to find information.
1. ALWAYS search before answering.
2. If the tool returns no results, say "I couldn't find that document."
3. Do not make up information. Use ONLY the content returned by the tool.
"""

model = get_llm(temperature=0)
tools = [search_knowledge_base]

research_agent = create_react_agent(
    model, 
    tools, 
    prompt=SYSTEM_PROMPT 
)