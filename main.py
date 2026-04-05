from app.services.image_loader import load_images_from_directory
from app.services.metadata_extractor import extract_metadata
from app.pipeline.process_images import enrich_images_with_metadata
from app.state import AppState

def main():

    state = AppState()

    #load images from directory
    state.images = load_images_from_directory('data/images')

    #enrich images with metadata
    enrich_images_with_metadata(state)

    #ausgabe
    print(state)

if __name__ == "__main__":
    main()
    

