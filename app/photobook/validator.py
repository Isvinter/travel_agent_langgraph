"""Deterministischer Validator fuer LLM-Seitenbeschreibungen.

Prueft die LLM-Ausgabe auf Konsistenz VOR dem Rendering.
Fehlerhafte Seiten werden mit minimalen Eingriffen repariert:
  - Template erhalten, wenn es existiert (nur Slot-IDs korrigieren)
  - Template aus gleicher Kategorie waehlen, wenn unbekannt
  - grid_2x2 als letzte Instanz, wenn alles andere fehlschlaegt
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
    """Repariert eine fehlerhafte Seite mit minimalen Eingriffen.

    Priorität: Template erhalten > Slots korrigieren > Captions bewahren.
    Nur wenn das Template nicht existiert, wird auf ein passendes Ersatz-Template
    der gleichen Kategorie oder grid_2x2 als letzte Instanz zurückgegriffen.
    """
    templates = load_all_templates()
    image_indices = [
        s["image_index"] for s in page.slots
        if s.get("image_index") is not None and s["image_index"] >= 0
    ]

    # Template existiert nicht → nächstes aus gleicher Kategorie wählen
    if page.template_id not in templates:
        category = "grid"
        # Versuche Kategorie des ursprünglichen Templates zu ermitteln
        for t in templates.values():
            if t.id == page.template_id or t.category == page.template_id:
                category = t.category
                break
        same_category = [t for t in templates.values() if t.category == category]
        for t in sorted(same_category, key=lambda t: abs(t.min_images - len(image_indices))):
            if t.min_images <= len(image_indices) <= t.max_images:
                page.template_id = t.id
                break
        else:
            page.template_id = "grid_2x2"

    template = templates[page.template_id]
    image_slot_ids = [s.id for s in template.slots if s.type == "image"]

    # Slots reparieren: korrekte Slot-IDs zuweisen, Captions erhalten
    repaired_slots = []
    for i, img_idx in enumerate(image_indices):
        if i >= len(image_slot_ids):
            break
        slot_id = image_slot_ids[i]
        # Caption aus passendem Original-Slot übernehmen
        orig_caption = ""
        for orig_slot in page.slots:
            if orig_slot.get("image_index") == img_idx and orig_slot.get("caption"):
                orig_caption = orig_slot["caption"]
                break
        slot_data = {"slot_id": slot_id, "image_index": img_idx}
        if orig_caption:
            slot_data["caption"] = orig_caption
        repaired_slots.append(slot_data)

    return PageDescription(
        template_id=page.template_id,
        page_type=page.page_type,
        slots=repaired_slots,
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
