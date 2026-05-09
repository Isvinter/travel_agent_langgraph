import logging

from app.state import AppState, ImageCluster
from app.services.clustering_images import cluster_images

logger = logging.getLogger(__name__)


def clustering_image_node(state: AppState) -> AppState:
    if not state.images:
        logger.warning("No images available for clustering.")
        return state

    # Cluster the images and store the results in the state
    try:
        raw_clusters = cluster_images(state.images)
        state.image_clusters = [
            ImageCluster(
                id=i,
                images=[img.path for img in c["images"]],
                center_lat=c["center_lat"],
                center_lon=c["center_lon"],
            )
            for i, c in enumerate(raw_clusters)
        ]
    except Exception as e:
        logger.error("Image clustering failed: %s — continuing without clusters", e)
        state.image_clusters = []

    logger.info("Clustered %s images into %s clusters.", len(state.images), len(state.image_clusters))
    
    return state