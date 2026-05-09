from app.state import AppState
from app.photobook.generate import generate_photobook_pages
from app.nodes.plan_photobook_node import _get_photobook_context


def generate_photobook_node(state: AppState) -> AppState:
    print("🎨 Generiere Fotobuch-Seiten (LLM Pass 2)...")
    if not state.photobook_plan:
        print("⚠️ Kein Layout-Plan vorhanden.")
        return state
    gpx_dict, preset = _get_photobook_context(state)
    try:
        pages = generate_photobook_pages(
            plan=state.photobook_plan, images=state.photobook_images,
            gpx_stats=gpx_dict, notes=state.notes, model=state.model,
            preset=preset,
        )
        state.photobook_pages = pages
        print(f"✅ {len(pages)} Fotobuch-Seiten generiert.")
    except Exception as e:
        print(f"❌ Fotobuch-Generierung fehlgeschlagen: {e}")
        state.photobook_pages = []
    return state
