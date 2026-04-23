from langgraph.graph import StateGraph
from app.state import AppState, AVAILABLE_MODELS
from app.nodes.process_gpx import process_gpx_node
from app.nodes.load_images import load_images_node
from app.nodes.extract_metadata import metadata_node
from app.nodes.generate_map import generate_map_image_node
from app.nodes.clustering_image_node import clustering_image_node
from app.nodes.load_tour_notes_node import load_tour_notes_node
from app.nodes.select_images_node import select_images_node
from app.nodes.generate_blogpost import generate_blog_post_node


def select_model() -> str:
    """Interaktive Model-Auswahl am Workflow-Start."""
    print("\nVerfügbare Ollama-Modelle:")
    for i, m in enumerate(AVAILABLE_MODELS, 1):
        print(f"  {i}. {m}")
    print(f"  {len(AVAILABLE_MODELS) + 1}. (sonstiges)")
    while True:
        choice = input("\nModel wählen (1-3, oder 4 für eigenes Modell): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(AVAILABLE_MODELS):
            return AVAILABLE_MODELS[int(choice) - 1]
        elif choice == str(len(AVAILABLE_MODELS) + 1):
            model = input("Eigenes Modell eingeben: ").strip()
            if model:
                return model
        print("Ungültige Auswahl, bitte versuche es erneut.")


def run_pipeline():
    """Build und ausfuhren des Workflows mit interaktiver Model-Auswahl."""
    state = AppState()
    state.model = select_model()
    print(f"\nSelected model: {state.model}")
    graph = build_graph()
    result = graph.invoke(state)
    return result


def build_graph() -> StateGraph[AppState]:
    builder = StateGraph(AppState)

    # Add GPX processing node
    builder.add_node("process_gpx", process_gpx_node)

    # Add image processing nodes
    builder.add_node("load_images", load_images_node)
    builder.add_node("extract_metadata", metadata_node)
    builder.add_node("generate_map_image", generate_map_image_node)
    builder.add_node("clustering_images", clustering_image_node)
    builder.add_node("load_tour_notes", load_tour_notes_node)
    builder.add_node("select_images", select_images_node)
    builder.add_node("generate_blog_post", generate_blog_post_node)

    # Set entry point to GPX processing
    builder.set_entry_point("process_gpx")

    # Define the flow: process_gpx -> load_images -> extract_metadata
    builder.add_edge("process_gpx", "load_images")
    builder.add_edge("load_images", "extract_metadata")
    builder.add_edge("extract_metadata", "clustering_images")
    builder.add_edge("clustering_images", "generate_map_image")
    builder.add_edge("generate_map_image", "load_tour_notes")
    builder.add_edge("load_tour_notes", "select_images")
    builder.add_edge("select_images", "generate_blog_post")


    # Set finish point
    builder.set_finish_point("generate_blog_post")

    return builder.compile()
