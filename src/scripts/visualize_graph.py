# src/scripts/visualize_graph.py
import sys
import os

# Path Hack
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.orchestrator.graph import graph

def generate_graph_image():
    print("Generating Graph Topology...")
    
    try:
        # Get the mermaid syntax (Flowchart definition)
        mermaid_png = graph.get_graph(xray=True).draw_mermaid_png()
        
        output_path = "glados_architecture.png"
        with open(output_path, "wb") as f:
            f.write(mermaid_png)
            
        print(f"Success! Graph saved to: {os.path.abspath(output_path)}")
        print("Open this file to see exactly how your Supervisor and Agents are connected.")
        
    except Exception as e:
        print(f"Could not generate graph: {e}")
        print("Note: You need 'grandalf' or similar layout engine installed, or run this in a conceptual sense.")

if __name__ == "__main__":
    generate_graph_image()