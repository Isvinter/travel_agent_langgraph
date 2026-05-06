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

    # --- Debug: zeige Seiten vor Validierung ---
    print(f"  Seiten vor Validierung: {len(state.photobook_pages)}")
    for i, p in enumerate(state.photobook_pages):
        text_slots = [s for s in p.slots if "text" in s]
        title_slot = next((s for s in p.slots if s.get("slot_id") == "title"), None)
        caption_slots = [s for s in p.slots if s.get("slot_id") != "title" and "text" in s]
        print(f"  Seite {i+1} ({p.template_id}): title={title_slot.get('text','')[:40] if title_slot else 'NONE'}, {len(caption_slots)} caption(s)")

    validated_pages, warnings = validate_all_pages(state.photobook_pages)
    if warnings:
        for w in warnings:
            print(f"⚠️ Validator: {w}")

    # --- Debug: zeige Seiten nach Validierung ---
    print(f"  Seiten nach Validierung: {len(validated_pages)}")
    for i, p in enumerate(validated_pages):
        text_slots = [s for s in p.slots if "text" in s]
        title_slot = next((s for s in p.slots if s.get("slot_id") == "title"), None)
        caption_slots = [s for s in p.slots if s.get("slot_id") != "title" and "text" in s]
        print(f"  Seite {i+1} ({p.template_id}): title={title_slot.get('text','')[:40] if title_slot else 'NONE'}, {len(caption_slots)} caption(s)")
        for cs in caption_slots:
            print(f"    {cs.get('slot_id')}: '{cs.get('text','')[:60]}'")

    state.photobook_pages = validated_pages

    # --- Bilder komprimieren ---
    if not state.photobook_timestamp:
        state.photobook_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    timestamp = state.photobook_timestamp
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

    # --- Status updaten mit komprimierten Bildpfaden ---
    state.photobook_images = compressed_images

    # --- Rendern mit komprimierten Bildern ---
    try:
        html = render_photobook(validated_pages, compressed_images)
        state.photobook_html = html

        # HTML-Datei speichern (zur Inspektion und Debugging)
        html_dir = Path(OUTPUT_DIR) / f"photobook_{timestamp}"
        html_dir.mkdir(parents=True, exist_ok=True)
        html_path = html_dir / f"{timestamp}_photobook.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        state.photobook_html_path = str(html_path)
        print(f"✅ Fotobuch-HTML gerendert ({len(html)} Zeichen).")
        print(f"📄 HTML gespeichert: {html_path}")
    except Exception as e:
        print(f"❌ Fehler beim Rendern: {e}")
    return state
