# src/app.py
import sys
import os
import re
import json

if os.getcwd() not in sys.path:
    sys.path.append(os.getcwd())

import chainlit as cl
from langchain_core.messages import HumanMessage
from src.core.voice import generate_speech

GRAPH = None

def get_graph():
    global GRAPH
    if GRAPH is None:
        try:
            from src.orchestrator.graph import graph
            GRAPH = graph
        except Exception as e:
            raise ImportError(f"Could not load Orchestrator: {e}")
    return GRAPH

@cl.on_chat_start
async def start():
    cl.user_session.set("thread_id", cl.user_session.get("id"))
    try:
        get_graph()
        await cl.Message(
            content="**Unraid Assistant Online.**\n\nI can help with Home Control, Finance, Research, and System Admin.",
            author="GLaDOS"
        ).send()
    except Exception as e:
        await cl.Message(content=f"**CRITICAL ERROR**:\n`{e}`", author="System").send()

@cl.on_message
async def main(message: cl.Message):
    graph = get_graph()
    thread_id = cl.user_session.get("thread_id")
    config = {"configurable": {"thread_id": thread_id}}
    
    inputs = {"messages": [HumanMessage(content=message.content)]}
    
    # --- PERSISTENT STATE ---
    active_steps = {} # "supervisor", "routing", "agent", "tool", "thought"
    final_text_buffer = ""

    # LIST OF AGENTS (Added "general_chat" here!)
    AGENTS = ["home_agent", "research_agent", "finance_agent", "scheduler_agent", "system_admin", "general_chat"]

    async for event in graph.astream_events(inputs, config=config, version="v1"):
        kind = event["event"]
        name = event["name"]
        data = event["data"]

        # ==================================================================================
        # 1. SUPERVISOR (ROOT)
        # ==================================================================================
        if kind == "on_chain_start" and name == "supervisor":
            step = cl.Step(name="Supervisor", type="process")
            await step.send()
            active_steps["supervisor"] = step
            
            # Create a specific Child Step for the Routing Logic
            routing_step = cl.Step(name="Dispatcher", type="process", parent_id=step.id)
            await routing_step.send()
            active_steps["routing"] = routing_step

        elif kind == "on_chain_end" and name == "supervisor":
            if "routing" in active_steps:
                routing_step = active_steps.pop("routing")
                output = data.get("output", {})
                next_step = output.get("next_step", "Unknown")
                
                json_content = json.dumps(output, indent=2)
                routing_step.output = f"```json\n{json_content}\n```\n\n**Decision: {next_step}**"
                await routing_step.update()

        # ==================================================================================
        # 2. AGENTS (CHILD)
        # ==================================================================================
        elif kind == "on_chain_start" and name in AGENTS:
            # Clean up previous steps
            if "thought" in active_steps: await active_steps.pop("thought").update()
            if "tool" in active_steps: await active_steps.pop("tool").update()
            if "agent" in active_steps: await active_steps.pop("agent").update()
            
            parent_id = active_steps["supervisor"].id if "supervisor" in active_steps else None
            
            # For General Chat, we might want to hide the step title or keep it. Keeping it for consistency.
            step = cl.Step(name=name, type="process", parent_id=parent_id)
            await step.send()
            active_steps["agent"] = step
            
            final_text_buffer = "" 

        elif kind == "on_chain_end" and name in AGENTS:
            if "thought" in active_steps: await active_steps.pop("thought").update()
            if "agent" in active_steps: await active_steps.pop("agent").update()

        # ==================================================================================
        # 3. TOOLS (GRANDCHILD)
        # ==================================================================================
        elif kind == "on_tool_start":
            if "thought" in active_steps: await active_steps.pop("thought").update()

            parent_id = active_steps["agent"].id if "agent" in active_steps else None
            if not parent_id and "supervisor" in active_steps: parent_id = active_steps["supervisor"].id
            
            step = cl.Step(name=name, type="tool", parent_id=parent_id, language="json")
            
            inp = data.get("input")
            if isinstance(inp, dict):
                step.input = json.dumps(inp, indent=2)
            else:
                step.input = str(inp)
                
            await step.send()
            active_steps["tool"] = step
            
            final_text_buffer = ""

        elif kind == "on_tool_end":
            if "tool" in active_steps:
                step = active_steps.pop("tool")
                out = data.get("output")
                out_str = str(out)
                
                if out_str.strip().startswith("{") or out_str.strip().startswith("["):
                    step.language = "json"
                    try:
                        parsed = json.loads(out_str)
                        step.output = json.dumps(parsed, indent=2)
                    except:
                        step.output = out_str
                else:
                    step.language = "text"
                    step.output = out_str
                await step.update()

        # ==================================================================================
        # 4. STREAMING
        # ==================================================================================
        elif kind == "on_chat_model_stream":
            metadata = event.get("metadata", {})
            langgraph_node = metadata.get("langgraph_node", "")
            
            chunk = data["chunk"]
            content = chunk.content
            
            if content:
                # CASE A: SUPERVISOR (Stream to Routing Step)
                if langgraph_node == "supervisor":
                    if "routing" in active_steps:
                        await active_steps["routing"].stream_token(content)
                
                # CASE B: AGENTS
                else:
                    if "agent" in active_steps and "thought" not in active_steps:
                        step = cl.Step(name="Reasoning", type="process", parent_id=active_steps["agent"].id)
                        await step.send()
                        active_steps["thought"] = step
                    
                    if "thought" in active_steps:
                        await active_steps["thought"].stream_token(content)
                    
                    final_text_buffer += content

        # ==================================================================================
        # 5. CLEANUP
        # ==================================================================================
        elif kind == "on_chat_model_end":
            output_msg = data.get("output")
            has_tool_calls = False
            if hasattr(output_msg, "tool_calls") and output_msg.tool_calls:
                has_tool_calls = True
            
            if has_tool_calls:
                final_text_buffer = ""
                if "thought" in active_steps:
                    await active_steps.pop("thought").update()

    # --- FINAL MESSAGE ---
    for key in list(active_steps.keys()):
        await active_steps[key].update()

    if final_text_buffer:
        final_msg = cl.Message(content=final_text_buffer, author="GLaDOS")
        await final_msg.send()

        clean_text = re.sub(r'```.*?```', '', final_text_buffer, flags=re.DOTALL).strip()
        if clean_text:
            audio_bytes = await generate_speech(clean_text)
            if audio_bytes:
                element = cl.Audio(
                    name="voice.wav", 
                    content=audio_bytes, 
                    display="inline",
                    auto_play=True
                )
                final_msg.elements = [element]
                await final_msg.update()