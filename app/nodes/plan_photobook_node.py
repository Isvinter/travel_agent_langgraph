from app.state import AppState
from app.photobook.plan import plan_photobook_layout


def plan_photobook_node(state: AppState) -> AppState:
    print("📋 Plane Fotobuch-Layout (LLM Pass 1)...")
    if not state.photobook_images:
        print("⚠️ Keine Bilder fuer Fotobuch-Planung vorhanden.")
        return state
    try:
        gpx_dict = state.gpx_stats.model_dump() if state.gpx_stats else {}
    except Exception:
        gpx_dict = {}
    try:
        plan = plan_photobook_layout(
            images=state.photobook_images, gpx_stats=gpx_dict, notes=state.notes,
            weather=state.weather, poi_list=state.poi_list, model=state.model,
        )
        state.photobook_plan = plan
        print(f"✅ Layout-Planung abgeschlossen: {len(plan.get('pages', []))} Seiten geplant.")
    except Exception as e:
        print(f"❌ Fotobuch-Planung fehlgeschlagen: {e}")
        state.photobook_plan = {"pages": []}
    return state
