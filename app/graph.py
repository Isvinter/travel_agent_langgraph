from typing import Callable, Optional
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

# Event emitter callback signature: (stage: str, status: str, message: str) -> None
EventEmitter = Callable[[str, str, str], None]

NODE_NAMES = {
    "process_gpx": "GPX-Analyse",
    "load_images": "Bilder laden",
    "extract_metadata": "Metadaten extrahieren",
    "clustering_images": "Bilder gruppieren",
    "generate_map_image": "Karte generieren",
    "load_tour_notes": "Notizen laden",
    "select_images": "Bilder auswählen",
    "generate_blog_post": "Blogpost generieren",
}


def _wrap_node(node_fn, node_name: str, emitter: Optional[EventEmitter]):
    """Wrap a pipeline node with progress event emission."""
    display_name = NODE_NAMES.get(node_name, node_name)

    def wrapped(state: AppState) -> AppState:
        if emitter:
            emitter(node_name, "running", f"{display_name} wird ausgeführt…")
        try:
            result = node_fn(state)
            if emitter:
                emitter(node_name, "done", f"{display_name} abgeschlossen.")
            return result
        except Exception as e:
            if emitter:
                emitter(node_name, "error", f"Fehler in {display_name}: {e}")
            raise

    return wrapped


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


def build_graph(event_emitter: Optional[EventEmitter] = None) -> StateGraph[AppState]:
    builder = StateGraph(AppState)

    # Wähle Node-Funktionen (ggf. mit Event-Wrapper)
    pgn = _wrap_node(process_gpx_node, "process_gpx", event_emitter) if event_emitter else process_gpx_node
    lin = _wrap_node(load_images_node, "load_images", event_emitter) if event_emitter else load_images_node
    emn = _wrap_node(metadata_node, "extract_metadata", event_emitter) if event_emitter else metadata_node
    cin = _wrap_node(clustering_image_node, "clustering_images", event_emitter) if event_emitter else clustering_image_node
    gmi = _wrap_node(generate_map_image_node, "generate_map_image", event_emitter) if event_emitter else generate_map_image_node
    ltn = _wrap_node(load_tour_notes_node, "load_tour_notes", event_emitter) if event_emitter else load_tour_notes_node
    sin = _wrap_node(select_images_node, "select_images", event_emitter) if event_emitter else select_images_node
    gbp = _wrap_node(generate_blog_post_node, "generate_blog_post", event_emitter) if event_emitter else generate_blog_post_node

    builder.add_node("process_gpx", pgn)
    builder.add_node("load_images", lin)
    builder.add_node("extract_metadata", emn)
    builder.add_node("generate_map_image", gmi)
    builder.add_node("clustering_images", cin)
    builder.add_node("load_tour_notes", ltn)
    builder.add_node("select_images", sin)
    builder.add_node("generate_blog_post", gbp)

    builder.set_entry_point("process_gpx")

    builder.add_edge("process_gpx", "load_images")
    builder.add_edge("load_images", "extract_metadata")
    builder.add_edge("extract_metadata", "clustering_images")
    builder.add_edge("clustering_images", "generate_map_image")
    builder.add_edge("generate_map_image", "load_tour_notes")
    builder.add_edge("load_tour_notes", "select_images")
    builder.add_edge("select_images", "generate_blog_post")

    builder.set_finish_point("generate_blog_post")

    return builder.compile()
