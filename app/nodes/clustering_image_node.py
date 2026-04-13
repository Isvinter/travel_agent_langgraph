from app.state import AppState
from app.services.clustering_images import cluster_images

def clustering_image_node(state: AppState) -> AppState:
    if not state.images:
        print("⚠️ No images available for clustering.")
        return state

    # Cluster the images and store the results in the state
    state.image_clusters = cluster_images(state.images)

    print(f"DEBUG: Clustered {len(state.images)} images into {len(state.image_clusters)} clusters.")
    
    return state