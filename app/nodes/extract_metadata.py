# app/nodes/extract_metadata.py

from app.state import AppState
from app.pipeline.process_images import enrich_images_with_metadata


def metadata_node(state: AppState) -> AppState:
    print("📷 Extracting image metadata...")
    try:
        enrich_images_with_metadata(state)
    except Exception as e:
        print(f"❌ Metadata extraction failed: {e} — continuing with unenriched images")
    return state