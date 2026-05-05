"""Deterministischer Validator fuer LLM-Seitenbeschreibungen.

Prueft die LLM-Ausgabe auf Konsistenz VOR dem Rendering.
Fehlerhafte Seiten werden in ein grid_2x2 Fallback-Layout umgewandelt.
"""

from typing import List
from app.state import PageDescription
from app.photobook.template_loader import load_all_templates


def validate_page(page: PageDescription, templates: dict = None) -> List[str]:
    """Prueft eine einzelne Seite auf Fehler. Gibt Liste von Fehlermeldungen zurueck."""
    errors = []
    if templates is None:
        templates = load_all_templates()

    if page.template_id not in templates:
        errors.append(f"Template '{page.template_id}' existiert nicht im Katalog.")
        return errors

    template = templates[page.template_id]
    slot_defs = {s.id: s for s in template.slots}
    image_count = 0

    for slot in page.slots:
        slot_id = slot.get("slot_id", "")
        if slot_id not in slot_defs:
            errors.append(f"Slot '{slot_id}' existiert nicht im Template '{page.template_id}'.")
            continue

        if slot.get("image_index") is not None:
            if slot["image_index"] < 0:
                errors.append(f"Slot '{slot_id}': image_index {slot['image_index']} ist ungueltig.")
            else:
                image_count += 1

    if image_count > template.max_images:
        errors.append(
            f"Zu viele Bilder: {image_count} (Template '{page.template_id}' erlaubt max. {template.max_images} Bilder)."
        )
    if image_count < template.min_images:
        errors.append(
            f"Zu wenige Bilder: {image_count} (Template '{page.template_id}' benoetigt min. {template.min_images} Bilder)."
        )

    # Pruefe dass alle mandatory slots (image type, nicht optional) befuellt sind
    mandatory_ids = {s.id for s in template.slots if not s.optional and s.type != "caption"}
    filled_ids = {s.get("slot_id", "") for s in page.slots if s.get("slot_id") in mandatory_ids}
    missing = mandatory_ids - filled_ids
    for mid in missing:
        slot_def = slot_defs[mid]
        if slot_def.type == "image":
            errors.append(f"Pflicht-Slot '{mid}' ist nicht befuellt.")

    return errors


def enforce_fallback(page: PageDescription) -> PageDescription:
    """Wandelt eine fehlerhafte Seite in ein grid_2x2 Fallback-Layout um.

    Verteilt die Bilder gleichmaessig auf die 4 Grid-Slots. Bei < 4 Bildern
    bleiben die hinteren Slots leer (optional=True laut Template).
    """
    image_indices = [
        s["image_index"] for s in page.slots
        if s.get("image_index") is not None and s["image_index"] >= 0
    ]
    slot_ids = ["tl", "tr", "bl", "br"]
    fallback_slots = []
    for i, img_idx in enumerate(image_indices):
        if i < len(slot_ids):
            fallback_slots.append({"slot_id": slot_ids[i], "image_index": img_idx})
    return PageDescription(
        template_id="grid_2x2",
        page_type="single",
        slots=fallback_slots,
    )


def validate_all_pages(pages: List[PageDescription]) -> tuple[List[PageDescription], List[str]]:
    """Validiert alle Seiten. Fehlerhafte Seiten werden in Fallback umgewandelt."""
    # Templates nur einmal laden
    _templates = load_all_templates()
    validated = []
    warnings = []
    for i, page in enumerate(pages):
        errors = validate_page(page, _templates)
        if errors:
            warnings.append(f"Seite {i}: {', '.join(errors)}")
            validated.append(enforce_fallback(page))
        else:
            validated.append(page)
    return validated, warnings
