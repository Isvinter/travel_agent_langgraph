from pathlib import Path
from app.state import AppState
from app.services.image_loader import load_images_from_directory


def load_images_node(state: AppState) -> AppState:
    # Get the absolute path to ensure it works regardless of working directory
    base_dir = Path(__file__).parent.parent.parent  # Go up to project root
    images_dir = base_dir / "data" / "images"
    
    print(f"DEBUG: Looking for images in {images_dir}")
    print(f"DEBUG: Directory exists: {images_dir.exists()}")
    
    if images_dir.exists():
        image_count = len(list(images_dir.iterdir()))
        print(f"DEBUG: Found {image_count} items in directory")
    
    state.images = load_images_from_directory(str(images_dir))
    
    print(f"DEBUG: Loaded {len(state.images)} images")
    if state.images:
        print(f"DEBUG: First image: {state.images[0].path}")
    
    return state