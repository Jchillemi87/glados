# main.py
import sys
from langchain_core.messages import HumanMessage
from src.orchestrator.graph import graph

def run_interactive_mode():
    print("--- Unraid Assistant Sanity Check ---")
    print("Type 'quit' to exit.")
    
    # A unique ID for this session. 
    # If you run this script again with the same ID, it will remember you!
    config = {"configurable": {"thread_id": "sanity_check_1"}}

    while True:
        try:
            user_input = input("\nYou: ")
            if user_input.lower() in ["quit", "exit"]:
                break

            # Stream the events so we see what's happening
            events = graph.stream(
                {"messages": [HumanMessage(content=user_input)]}, 
                config=config, 
                stream_mode="values"
            )
            
            for event in events:
                # Print the AI's response (last message in the list)
                if "messages" in event:
                    last_msg = event["messages"][-1]
                    if last_msg.type == "ai":
                        print(f"Agent: {last_msg.content}")
                        
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    run_interactive_mode()