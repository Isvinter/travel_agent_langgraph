import logging
from typing import Callable, Optional
from langgraph.graph import StateGraph, END
from app.state import AppState, AVAILABLE_MODELS
from app.nodes.process_gpx import process_gpx_node
from app.nodes.load_images import load_images_node
from app.nodes.extract_metadata import metadata_node
from app.nodes.generate_map import generate_map_image_node
from app.nodes.clustering_image_node import clustering_image_node
from app.nodes.load_tour_notes_node import load_tour_notes_node
from app.nodes.select_images_node import select_images_node
from app.nodes.generate_blogpost import generate_blog_post_node
from app.nodes.enrich_weather_node import enrich_weather_node
from app.nodes.enrich_poi_node import enrich_poi_node
from app.nodes.review_content_node import review_content_node
from app.nodes.save_draft import save_draft_node
from app.nodes.persist_article import persist_article_node
from app.nodes.design_blogpost import design_blogpost_node
from app.nodes.generate_enriched_map import generate_enriched_map_node
from app.nodes.generate_pdf import generate_pdf_node
from app.nodes.select_photobook_images_node import select_photobook_images_node
from app.nodes.plan_photobook_node import plan_photobook_node
from app.nodes.generate_photobook_node import generate_photobook_node
from app.nodes.render_photobook_node import render_photobook_node
from app.nodes.generate_photobook_pdf_node import generate_photobook_pdf_node
from app.nodes.persist_photobook import persist_photobook_node

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
    "enrich_weather": "Wetterdaten abrufen",
    "enrich_poi": "POIs suchen",
    "review_content": "Inhalte prüfen",
    "persist_article": "Artikel speichern",
    "save_draft": "Draft speichern",
    "design_blogpost": "Design anwenden",
    "generate_pdf": "PDF generieren",
    "generate_enriched_map": "Angereicherte Karte generieren",
    "select_photobook_images": "Fotobuch: Bilder auswählen",
    "plan_photobook": "Fotobuch: Layout planen",
    "generate_photobook": "Fotobuch: Seiten generieren",
    "render_photobook": "Fotobuch: Rendern",
    "generate_photobook_pdf": "Fotobuch: PDF erstellen",
    "persist_photobook": "Fotobuch speichern",
}


logger = logging.getLogger(__name__)


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


def _add_wrapped(builder: StateGraph, name: str, fn: Callable, emitter: Optional[EventEmitter]):
    """Fügt einen Node hinzu, optional mit Event-Emitter-Wrapper."""
    node = _wrap_node(fn, name, emitter) if emitter else fn
    builder.add_node(name, node)


def select_model() -> str:
    """Interaktive Model-Auswahl am Workflow-Start."""
    logger.info("Verfügbare Ollama-Modelle:")
    for i, m in enumerate(AVAILABLE_MODELS, 1):
        logger.info("  %s. %s", i, m)
    logger.info("  %s. (sonstiges)", len(AVAILABLE_MODELS) + 1)
    while True:
        choice = input("\nModel wählen (1-3, oder 4 für eigenes Modell): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(AVAILABLE_MODELS):
            return AVAILABLE_MODELS[int(choice) - 1]
        elif choice == str(len(AVAILABLE_MODELS) + 1):
            model = input("Eigenes Modell eingeben: ").strip()
            if model:
                return model
        logger.info("Ungültige Auswahl, bitte versuche es erneut.")


def run_pipeline():
    """Build und ausfuhren des Workflows mit interaktiver Model-Auswahl."""
    state = AppState()
    state.model = select_model()
    logger.info("Selected model: %s", state.model)
    graph = build_graph()
    result = graph.invoke(state)
    if isinstance(result, dict):
        return AppState(**result)
    return result


def build_graph(event_emitter: Optional[EventEmitter] = None) -> StateGraph[AppState]:
    builder = StateGraph(AppState)

    # Blog/Analysis nodes
    _add_wrapped(builder, "process_gpx", process_gpx_node, event_emitter)
    _add_wrapped(builder, "load_images", load_images_node, event_emitter)
    _add_wrapped(builder, "extract_metadata", metadata_node, event_emitter)
    _add_wrapped(builder, "clustering_images", clustering_image_node, event_emitter)
    _add_wrapped(builder, "generate_map_image", generate_map_image_node, event_emitter)
    _add_wrapped(builder, "load_tour_notes", load_tour_notes_node, event_emitter)
    _add_wrapped(builder, "select_images", select_images_node, event_emitter)
    _add_wrapped(builder, "generate_blog_post", generate_blog_post_node, event_emitter)
    _add_wrapped(builder, "design_blogpost", design_blogpost_node, event_emitter)

    # Enrichment nodes
    _add_wrapped(builder, "enrich_weather", enrich_weather_node, event_emitter)
    _add_wrapped(builder, "enrich_poi", enrich_poi_node, event_emitter)
    _add_wrapped(builder, "review_content", review_content_node, event_emitter)
    _add_wrapped(builder, "generate_enriched_map", generate_enriched_map_node, event_emitter)
    _add_wrapped(builder, "persist_article", persist_article_node, event_emitter)
    _add_wrapped(builder, "save_draft", save_draft_node, event_emitter)
    _add_wrapped(builder, "generate_pdf", generate_pdf_node, event_emitter)

    # Photobook nodes
    _add_wrapped(builder, "select_photobook_images", select_photobook_images_node, event_emitter)
    _add_wrapped(builder, "plan_photobook", plan_photobook_node, event_emitter)
    _add_wrapped(builder, "generate_photobook", generate_photobook_node, event_emitter)
    _add_wrapped(builder, "render_photobook", render_photobook_node, event_emitter)
    _add_wrapped(builder, "generate_photobook_pdf", generate_photobook_pdf_node, event_emitter)
    _add_wrapped(builder, "persist_photobook", persist_photobook_node, event_emitter)

    builder.set_entry_point("process_gpx")

    builder.add_edge("process_gpx", "load_images")
    builder.add_edge("load_images", "extract_metadata")
    builder.add_edge("extract_metadata", "clustering_images")
    builder.add_edge("clustering_images", "generate_map_image")
    builder.add_edge("generate_map_image", "load_tour_notes")

    # Mode-abhaengiges Routing NACH load_tour_notes:
    # Photobook überspringt die teuren Blog-Enrichment-Schritte
    def _route_after_notes(state: AppState) -> str:
        if state.output_config.mode == "photobook":
            return "select_photobook_images"
        return "enrich_weather"

    builder.add_conditional_edges(
        "load_tour_notes",
        _route_after_notes,
        {
            "select_photobook_images": "select_photobook_images",
            "enrich_weather": "enrich_weather",
        },
    )

    # Blog-Pfad: Enrichment + Content-Review (nur für Blog-Mode)
    builder.add_edge("enrich_weather", "enrich_poi")
    builder.add_edge("enrich_poi", "select_images")
    builder.add_edge("select_images", "review_content")
    builder.add_edge("review_content", "generate_enriched_map")
    builder.add_edge("generate_enriched_map", "generate_blog_post")

    # Photobook-Pfad
    builder.add_edge("select_photobook_images", "plan_photobook")
    builder.add_edge("plan_photobook", "generate_photobook")
    builder.add_edge("generate_photobook", "render_photobook")
    builder.add_edge("render_photobook", "generate_photobook_pdf")
    builder.add_edge("generate_photobook_pdf", "persist_photobook")
    builder.add_edge("persist_photobook", END)

    builder.add_edge("generate_blog_post", "design_blogpost")

    def _route_after_design(state: AppState) -> str:
        if state.output_config.review_enabled:
            return "save_draft"
        return "persist_article"

    builder.add_conditional_edges(
        "design_blogpost",
        _route_after_design,
        {
            "save_draft": "save_draft",
            "persist_article": "persist_article",
        },
    )

    # save_draft ends the pipeline (no PDF in draft mode)
    builder.add_edge("save_draft", END)

    def _should_generate_pdf(state: AppState) -> str:
        if state.output_config.pdf_export:
            return "generate_pdf"
        return END

    builder.add_conditional_edges(
        "persist_article",
        _should_generate_pdf,
        {"generate_pdf": "generate_pdf", END: END},
    )
    builder.add_edge("generate_pdf", END)

    return builder.compile()
