# app/nodes/load_images.py

from app.state import AppState
from app.services.image_loader import load_images_from_directory


def load_images_node(state: AppState) -> AppState:
    state.images = load_images_from_directory("data/images")
    return state