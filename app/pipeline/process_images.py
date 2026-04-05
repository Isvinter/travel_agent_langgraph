from app.state import AppState
from app.services.metadata_extractor import extract_metadata

def enrich_images_with_metadata(state: AppState):

    for image_data in state.images:
        metadata = extract_metadata(image_data.path)
        
        image_data.timestamp = metadata.get["timestamp"]
        image_data.latitude = metadata.get["latitude"]
        image_data.longitude = metadata.get["longitude"]

