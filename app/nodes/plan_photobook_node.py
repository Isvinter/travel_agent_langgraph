from app.state import AppState
from app.photobook.plan import plan_photobook_layout
from app.photobook.presets import get_photobook_preset


def _get_photobook_context(state: AppState):
    """Extrahiert gpx_dict und preset aus AppState (gemeinsam fuer Photobook-Nodes)."""
    try:
        gpx_dict = state.gpx_stats.model_dump() if state.gpx_stats else {}
    except Exception:
        gpx_dict = {}
    preset = get_photobook_preset(state.output_config.photobook_preset)
    return gpx_dict, preset


def plan_photobook_node(state: AppState) -> AppState:
    print("📋 Plane Fotobuch-Layout (LLM Pass 1)...")
    if not state.photobook_images:
        print("⚠️ Keine Bilder fuer Fotobuch-Planung vorhanden.")
        return state
    gpx_dict, preset = _get_photobook_context(state)
    try:
        plan = plan_photobook_layout(
            images=state.photobook_images, gpx_stats=gpx_dict, notes=state.notes,
            weather=state.weather, poi_list=state.poi_list, model=state.model,
            page_range=state.output_config.photobook.page_range,
            preset=preset,
        )
        state.photobook_plan = plan
        print(f"✅ Layout-Planung abgeschlossen: {len(plan.get('pages', []))} Seiten geplant.")
    except Exception as e:
        print(f"❌ Fotobuch-Planung fehlgeschlagen: {e}")
        state.photobook_plan = {"pages": []}
    return state
