from app.state import AppState
from app.photobook.image_selector import select_photobook_images
from app.photobook.presets import get_photobook_preset


def select_photobook_images_node(state: AppState) -> AppState:
    print("📸 Waehle Bilder fuer das Fotobuch aus...")
    if not state.images:
        print("⚠️ Keine Bilder fuer Fotobuch-Auswahl vorhanden.")
        return state
    try:
        gpx_dict = state.gpx_stats.model_dump() if state.gpx_stats else {}
    except Exception:
        gpx_dict = {}
    preset = get_photobook_preset(state.output_config.photobook_preset)
    try:
        selected = select_photobook_images(
            images=state.images, gpx_stats=gpx_dict, notes=state.notes,
            model=state.model, photo_count=state.output_config.photobook.photo_count,
            preset=preset,
        )
        state.photobook_images = selected
        print(f"✅ {len(selected)} Bilder fuer das Fotobuch ausgewaehlt.")
    except Exception as e:
        print(f"❌ Fotobuch-Bildauswahl fehlgeschlagen: {e} — verwende alle Bilder")
        max_count = state.output_config.photobook.photo_count
        state.photobook_images = state.images[:max_count]
    return state
