# app/nodes/persist_photobook.py
from app.state import AppState
from app.services.persist_photobook import persist_photobook


def persist_photobook_node(state: AppState) -> AppState:
    """Persistiert das generierte Fotobuch in der Datenbank."""
    print("💾 Persisting photobook to database...")

    photobook_id = persist_photobook(
        gpx_stats=state.gpx_stats,
        photobook_images=state.photobook_images,
        photobook_pages=state.photobook_pages,
        photobook_html=state.photobook_html,
        photobook_html_path=state.photobook_html_path,
        photobook_pdf_path=state.photobook_pdf_path,
        photobook_size=state.output_config.photobook.size,
        gpx_file=state.gpx_file,
        model=state.model,
        notes=state.notes,
    )

    if photobook_id:
        print(f"✅ Photobook persisted with ID: {photobook_id}")
        state.metadata["photobook_id"] = photobook_id
    else:
        print("⚠️ Photobook was not persisted (DB error).")
        state.metadata["photobook_id"] = None

    return state
