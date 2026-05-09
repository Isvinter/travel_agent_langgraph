# app/nodes/extract_metadata.py
import logging

from app.state import AppState
from app.pipeline.process_images import enrich_images_with_metadata

logger = logging.getLogger(__name__)


def metadata_node(state: AppState) -> AppState:
    logger.info("Extracting image metadata...")
    try:
        enrich_images_with_metadata(state)
    except Exception as e:
        logger.error("Metadata extraction failed: %s — continuing with unenriched images", e)
    return state