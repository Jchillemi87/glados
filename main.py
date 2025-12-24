import sys
import uuid
from langchain_core.messages import HumanMessage
from src.orchestrator.graph import graph

def run_interactive_mode():
    print("--- Unraid Assistant (Supervisor Mode) ---")
    
    if len(sys.argv) > 1:
        thread_id = sys.argv[1]
    else:
        thread_id = str(uuid.uuid4())[:8]

    print(f"Session ID: {thread_id}")
    print("Type 'quit' to exit.")
    
    config = {"configurable": {"thread_id": thread_id}}

    while True:
        try:
            user_input = input("\nYou: ")
            if user_input.lower() in ["quit", "exit"]:
                break
            
            events = graph.stream(
                {"messages": [HumanMessage(content=user_input)]}, 
                config=config, 
                stream_mode="values"
            )
            
            for event in events:
                if "messages" in event:
                    last_msg = event["messages"][-1]
                    
                    # Print AI Speech
                    if last_msg.type == "ai":
                        if last_msg.content:
                            print(f"Agent: {last_msg.content}")
                        
                        # Print Tool Calls
                        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                            for tool_call in last_msg.tool_calls:
                                name = tool_call['name']
                                args = tool_call['args']
                                print(f"   >>> [TOOL CALL]: {name}({args})")

                    # Print Tool Outputs (good for deep debug)
                    elif last_msg.type == "tool":
                         print(f"   >>> [TOOL RESULT]: {last_msg.content[:100]}...") 

        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    run_interactive_mode()