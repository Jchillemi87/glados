# src/capabilities/research/agent.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage  # <--- 1. ADD THIS IMPORT
from langgraph.prebuilt import create_react_agent
from src.core.llm import get_llm
from src.capabilities.research.tools import search_knowledge_base

# 1. The Persona
SYSTEM_PROMPT = """You are the Research Specialist.
Your ONLY job is to query the 'search_knowledge_base' tool to find information.
1. ALWAYS search before answering.
2. If the tool returns no results, say "I couldn't find that document."
3. Do not make up information. Use ONLY the content returned by the tool.
"""

# 2. The Model
model = get_llm(temperature=0)

# 3. The Tools
tools = [search_knowledge_base]

# 4. The Agent (Sub-Graph)
# FIX: Use 'prompt' (for compatibility) and wrap text in SystemMessage
# The "Production Standard" way
research_agent = create_react_agent(
    model, 
    tools, 
    # Use 'state_modifier' instead of 'prompt'.
    state_modifier=SystemMessage(content=SYSTEM_PROMPT)
)