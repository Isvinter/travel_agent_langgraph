# app/nodes/extract_metadata.py

from app.state import AppState
from app.pipeline.process_images import enrich_images_with_metadata


def metadata_node(state: AppState) -> AppState:
    enrich_images_with_metadata(state)
    return state