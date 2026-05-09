import logging

from app.state import AppState
from app.services.clustering_images import cluster_images

logger = logging.getLogger(__name__)


def clustering_image_node(state: AppState) -> AppState:
    if not state.images:
        logger.warning("No images available for clustering.")
        return state

    # Cluster the images and store the results in the state
    try:
        state.image_clusters = cluster_images(state.images)
    except Exception as e:
        logger.error("Image clustering failed: %s — continuing without clusters", e)
        state.image_clusters = []

    logger.info("Clustered %s images into %s clusters.", len(state.images), len(state.image_clusters))
    
    return state