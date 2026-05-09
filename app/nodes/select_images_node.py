# app/nodes/select_images_node.py
import logging
import math

from app.state import AppState
from app.services.image_selector import select_images_for_blog

logger = logging.getLogger(__name__)


def select_images_node(state: AppState) -> AppState:
    """Wählt die besten Bilder für den Blogpost mit einem multimodalen LLM."""
    n = len(state.images)
    target = math.ceil(state.output_config.wildcard_max * 1.5)
    target = min(target, n)  # nicht mehr als verfügbar
    logger.info("Oversampling: selecting %s images (max %s) from %s images...", target, state.output_config.wildcard_max, n)

    try:
        selected = select_images_for_blog(
            images=[img.model_dump() for img in state.images],
            target_count=target,
            model=state.model,
        )
    except Exception as e:
        logger.error("Image selection failed: %s — using all images as fallback", e)
        selected = [{"path": img.path} for img in state.images[:target]]

    # Vom LLM ausgewählte Bild-Dicts zurück auf die originalen ImageData-Objekte abbilden
    img_by_path = {img.path: img for img in state.images}
    state.selected_images = [
        img_by_path[sel["path"]]
        for sel in selected
        if sel.get("path") in img_by_path
    ]
    state.selected_image_count = len(state.selected_images)

    logger.info("Selected %s images for blog post", len(state.selected_images))
    return state
