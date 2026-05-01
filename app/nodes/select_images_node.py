# app/nodes/select_images_node.py
from app.state import AppState
from app.services.image_selector import select_images_for_blog


def select_images_node(state: AppState) -> AppState:
    """Wählt die besten Bilder für den Blogpost mit einem multimodalen LLM."""
    import math
    n = len(state.images)
    target = math.ceil(state.output_config.wildcard_max * 1.5)
    target = min(target, n)  # nicht mehr als verfügbar
    print(f"📸 Oversampling: selecting {target} images (max {state.output_config.wildcard_max}) from {n} images...")

    selected = select_images_for_blog(
        images=[img.model_dump() for img in state.images],
        target_count=target,
        model=state.model,
    )

    # Vom LLM ausgewählte Bild-Dicts zurück auf die originalen ImageData-Objekte abbilden
    img_by_path = {img.path: img for img in state.images}
    state.selected_images = [
        img_by_path[sel["path"]]
        for sel in selected
        if sel.get("path") in img_by_path
    ]
    state.metadata["selected_image_count"] = len(state.selected_images)

    print(f"✅ Selected {len(selected)} images for blog post")
    return state
