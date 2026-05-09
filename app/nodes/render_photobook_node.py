import logging
import os
from datetime import datetime
from pathlib import Path
from app.state import AppState, ImageData
from app.photobook.renderer import render_photobook
from app.photobook.validator import validate_all_pages
from app.utils.image_utils import compress_image_to_jpeg
from app.config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def render_photobook_node(state: AppState) -> AppState:
    logger.info("Rendere Fotobuch als HTML...")
    if not state.photobook_pages:
        logger.warning("Keine Seiten zum Rendern vorhanden.")
        return state

    # --- Debug: zeige Seiten vor Validierung ---
    logger.info("Seiten vor Validierung: %s", len(state.photobook_pages))
    for i, p in enumerate(state.photobook_pages):
        text_slots = [s for s in p.slots if "text" in s]
        title_slot = next((s for s in p.slots if s.get("slot_id") == "title"), None)
        caption_slots = [s for s in p.slots if s.get("slot_id") != "title" and "text" in s]
        logger.info("Seite %s (%s): title=%s, %s caption(s)", i+1, p.template_id, title_slot.get('text','')[:40] if title_slot else 'NONE', len(caption_slots))

    validated_pages, warnings = validate_all_pages(state.photobook_pages)
    # Unterdrücke kosmetische "existiert nicht" Warnungen — enforce_fallback handled das
    real_warnings = [w for w in warnings if "existiert nicht im Preset" not in w]
    if real_warnings:
        for w in real_warnings:
            logger.warning("Validator: %s", w)

    # --- Debug: zeige Seiten nach Validierung ---
    logger.info("Seiten nach Validierung: %s", len(validated_pages))
    for i, p in enumerate(validated_pages):
        text_slots = [s for s in p.slots if "text" in s]
        title_slot = next((s for s in p.slots if s.get("slot_id") == "title"), None)
        caption_slots = [s for s in p.slots if s.get("slot_id") != "title" and "text" in s]
        logger.info("Seite %s (%s): title=%s, %s caption(s)", i+1, p.template_id, title_slot.get('text','')[:40] if title_slot else 'NONE', len(caption_slots))
        for cs in caption_slots:
            logger.info("  %s: '%s'", cs.get('slot_id'), cs.get('text','')[:60])

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
            logger.warning("Bild nicht gefunden, überspringe: %s", orig)
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
            logger.info("Bild %s/%s komprimiert: %s", idx + 1, len(state.photobook_images), out_name)
        else:
            logger.warning("Kompression fehlgeschlagen für %s, verwende Original", orig)
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
        logger.info("Fotobuch-HTML gerendert (%s Zeichen).", len(html))
        logger.info("HTML gespeichert: %s", html_path)
    except Exception as e:
        logger.error("Fehler beim Rendern: %s", e)
    return state
