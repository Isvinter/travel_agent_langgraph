from langgraph.graph import StateGraph
from app.state import AppState

from app.nodes.load_images import load_images_node
from app.nodes.extract_metadata import metadata_node

def build_graph() -> StateGraph[AppState]:
    builder = StateGraph(AppState)
    builder.add_node("load_images", load_images_node)
    builder.add_node("metadata", metadata_node)

    builder.add.entry_point("load_images")
    builder.add.edge("load_images", "metadata")

    builder.set_finish_point("metadata")

    return builder.compile()
