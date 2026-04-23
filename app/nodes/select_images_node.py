# app/nodes/select_images_node.py
from app.state import AppState
from app.services.image_selector import select_images_for_blog


def select_images_node(state: AppState) -> AppState:
    """Wählt die besten Bilder für den Blogpost mit einem multimodalen LLM."""
    n = len(state.images)
    target = 8
    print(f"📸 Selecting {target} images for blog post from {n} images...")

    selected = select_images_for_blog(
        images=[img.model_dump() for img in state.images],
        target_count=target,
        model=state.model,
    )

    state.selected_images = [state.images[i] for i in range(len(selected))]
    state.metadata["selected_image_count"] = len(selected)

    print(f"✅ Selected {len(selected)} images for blog post")
    return state
