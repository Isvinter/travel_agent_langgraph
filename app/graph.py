from langgraph.graph import StateGraph
from app.state import AppState
from app.pipeline.process_gpx import process_gpx_node

def build_graph() -> StateGraph[AppState]:
    builder = StateGraph(AppState)
    
    print("DEBUG graph.py: Adding process_gpx node")
    
    # Add GPX processing node
    builder.add_node("process_gpx", process_gpx_node)
    
    # Set entry point to GPX processing
    builder.set_entry_point("process_gpx")
    builder.set_finish_point("process_gpx")
    
    print("DEBUG graph.py: Graph compiled")
    return builder.compile()
