from langgraph.graph import StateGraph
from app.state import AppState
from app.nodes.process_gpx import process_gpx_node
from app.nodes.load_images import load_images_node
from app.nodes.extract_metadata import metadata_node

def build_graph() -> StateGraph[AppState]:
    builder = StateGraph(AppState)

    # Add GPX processing node
    builder.add_node("process_gpx", process_gpx_node)
    
    # Add image processing nodes
    builder.add_node("load_images", load_images_node)
    builder.add_node("extract_metadata", metadata_node)

    # Set entry point to GPX processing
    builder.set_entry_point("process_gpx")
    
    # Define the flow: process_gpx -> load_images -> extract_metadata
    builder.add_edge("process_gpx", "load_images")
    builder.add_edge("load_images", "extract_metadata")
    
    # Set finish point
    builder.set_finish_point("extract_metadata")

    return builder.compile()
