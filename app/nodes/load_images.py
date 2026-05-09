import logging
from pathlib import Path
from app.state import AppState
from app.services.image_loader import load_images_from_directory

logger = logging.getLogger(__name__)


def load_images_node(state: AppState) -> AppState:
    # Get the absolute path to ensure it works regardless of working directory
    base_dir = Path(__file__).parent.parent.parent  # Go up to project root
    images_dir = base_dir / "data" / "images"
    
    logger.info("Looking for images in %s", images_dir)
    logger.info("Directory exists: %s", images_dir.exists())
    
    if images_dir.exists():
        image_count = len(list(images_dir.iterdir()))
        logger.info("Found %s items in directory", image_count)
    
    # Falls bereits Bilder via API-Upload vorliegen, diese nicht überschreiben
    if state.images:
        logger.info("Using %s images provided via API upload", len(state.images))
    else:
        try:
            state.images = load_images_from_directory(str(images_dir))
        except Exception as e:
            logger.error("Image loading failed: %s — continuing without images", e)
            state.images = []
    
    logger.info("Loaded %s images", len(state.images))
    if state.images:
        logger.info("First image: %s", state.images[0].path)
    
    return state