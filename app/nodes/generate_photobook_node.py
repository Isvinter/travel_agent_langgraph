from app.state import AppState
from app.photobook.generate import generate_photobook_pages
from app.photobook.presets import get_photobook_preset


def generate_photobook_node(state: AppState) -> AppState:
    print("🎨 Generiere Fotobuch-Seiten (LLM Pass 2)...")
    if not state.photobook_plan:
        print("⚠️ Kein Layout-Plan vorhanden.")
        return state
    try:
        gpx_dict = state.gpx_stats.model_dump() if state.gpx_stats else {}
    except Exception:
        gpx_dict = {}
    preset = get_photobook_preset(state.output_config.photobook_preset)
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
