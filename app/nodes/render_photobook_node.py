import os
from datetime import datetime
from pathlib import Path
from app.state import AppState, ImageData
from app.photobook.renderer import render_photobook
from app.photobook.validator import validate_all_pages
from app.utils.image_utils import compress_image_to_jpeg
from app.config import OUTPUT_DIR


def render_photobook_node(state: AppState) -> AppState:
    print("🖨️ Rendere Fotobuch als HTML...")
    if not state.photobook_pages:
        print("⚠️ Keine Seiten zum Rendern vorhanden.")
        return state
    validated_pages, warnings = validate_all_pages(state.photobook_pages)
    if warnings:
        for w in warnings:
            print(f"⚠️ Validator: {w}")
    state.photobook_pages = validated_pages

    # --- Bilder komprimieren ---
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    images_dir = Path(OUTPUT_DIR) / f"photobook_{timestamp}" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    compressed_images = []
    for idx, img in enumerate(state.photobook_images):
        orig = img.path
        if not orig or not os.path.isfile(orig):
            print(f"⚠️ Bild nicht gefunden, überspringe: {orig}")
            compressed_images.append(img)
            continue

        basename = os.path.splitext(os.path.basename(orig))[0]
        out_name = f"{idx:02d}_{basename}.jpg"
        out_path = str(images_dir / out_name)

        result = compress_image_to_jpeg(orig, out_path)
        if result:
            compressed_images.append(ImageData(
                path=result,
                timestamp=img.timestamp,
                latitude=img.latitude,
                longitude=img.longitude,
            ))
            print(f"  ✅ Bild {idx + 1}/{len(state.photobook_images)} komprimiert: {out_name}")
        else:
            print(f"  ⚠️ Kompression fehlgeschlagen für {orig}, verwende Original")
            compressed_images.append(img)

    # --- Rendern mit komprimierten Bildern ---
    try:
        html = render_photobook(validated_pages, compressed_images)
        state.photobook_html = html
        print(f"✅ Fotobuch-HTML gerendert ({len(html)} Zeichen).")
    except Exception as e:
        print(f"❌ Fehler beim Rendern: {e}")
    return state
