from app.state import AppState
from app.photobook.renderer import render_photobook
from app.photobook.validator import validate_all_pages

OUTPUT_DIR = "output"


def render_photobook_node(state: AppState) -> AppState:
    print("🖨️ Rendere Fotobuch als HTML...")
    if not state.photobook_pages:
        print("⚠️ Keine Seiten zum Rendern vorhanden.")
        return state
    validated_pages, warnings = validate_all_pages(state.photobook_pages)
    if warnings:
        for w in warnings:
            print(f"⚠️ Validator: {w}")
    state.photobook_pages = validated_pages
    try:
        html = render_photobook(validated_pages, state.photobook_images)
        state.photobook_html = html
        print(f"✅ Fotobuch-HTML gerendert ({len(html)} Zeichen).")
    except Exception as e:
        print(f"❌ Fehler beim Rendern: {e}")
    return state
