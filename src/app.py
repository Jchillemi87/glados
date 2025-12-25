import sys
import os

# --- PATH HACK FOR CHAINLIT ---
# Chainlit runs this file as the entry point. We need to make sure the root
# of the project (P:\glados) is in sys.path so we can do "from src.core..."
if os.getcwd() not in sys.path:
    sys.path.append(os.getcwd())

import chainlit as cl
from langchain_core.messages import HumanMessage

# Lazy load graph to allow Chainlit UI to render even if backend is slow
GRAPH = None

def get_graph():
    global GRAPH
    if GRAPH is None:
        try:
            print("[DEBUG] Loading Graph...")
            from src.orchestrator.graph import graph
            GRAPH = graph
            print("[DEBUG] Graph Loaded Successfully.")
        except Exception as e:
            # Re-raise so the UI can catch it and display the error
            raise ImportError(f"Could not load Orchestrator: {e}")
    return GRAPH

@cl.on_chat_start
async def start():
    """
    Initializes the session.
    """
    # Set Thread ID for Memory
    cl.user_session.set("thread_id", cl.user_session.get("id"))
    
    try:
        # Attempt to load the graph immediately to surface errors on startup
        get_graph()
        
        await cl.Message(
            content="**Unraid Assistant Online.**\n\nI can help with Home Control, Finance, Research, and System Admin.",
            author="GLaDOS"
        ).send()
        
    except Exception as e:
        await cl.Message(
            content=f"**CRITICAL STARTUP ERROR**:\n\n`{str(e)}`\n\nCheck your console logs for details (SQL/Qdrant connection timeouts).",
            author="System"
        ).send()

@cl.on_message
async def main(message: cl.Message):
    """
    Main loop for processing user messages.
    """
    graph = get_graph()
    thread_id = cl.user_session.get("thread_id")
    config = {"configurable": {"thread_id": thread_id}}
    
    inputs = {"messages": [HumanMessage(content=message.content)]}
    
    msg = cl.Message(content="", author="GLaDOS")
    
    # We use astream_events to get real-time tokens
    async for event in graph.astream_events(inputs, config=config, version="v1"):
        kind = event["event"]
        
        # Only stream the final LLM tokens from the Agent (ignore Supervisor JSON)
        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if chunk.content:
                await msg.stream_token(chunk.content)
                
    await msg.send()