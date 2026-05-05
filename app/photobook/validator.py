"""Deterministischer Validator fuer LLM-Seitenbeschreibungen.

Prueft die LLM-Ausgabe auf Konsistenz VOR dem Rendering:
  - Slot-Konsistenz gegen Preset-Definition
  - Char-Limit-Overflow → Text kürzen
  - Variety-Checks (Cover, Back-to-Back, Text-Lücke, Bildanzahl-Monotonie, Gesamt-Variety)
"""

from typing import List
from app.state import PageDescription
from app.photobook.preset_loader import load_all_presets
from app.photobook.presets import get_any_preset, get_presets_by_image_count


def validate_page(page: PageDescription, presets: dict = None) -> List[str]:
    """Prueft eine einzelne Seite auf Fehler. Gibt Liste von Fehlermeldungen zurueck."""
    errors = []
    if presets is None:
        presets = load_all_presets()

    if page.template_id not in presets:
        errors.append(f"Preset '{page.template_id}' existiert nicht im Katalog.")
        return errors

    preset = presets[page.template_id]
    slot_defs = {s.id: s for s in preset.slots}
    image_count = 0

    for slot in page.slots:
        slot_id = slot.get("slot_id", "")
        if slot_id not in slot_defs:
            errors.append(f"Slot '{slot_id}' existiert nicht im Preset '{page.template_id}'.")
            continue

        slot_def = slot_defs[slot_id]

        if slot.get("image_index") is not None:
            if slot["image_index"] < 0:
                errors.append(f"Slot '{slot_id}': image_index {slot['image_index']} ist ungueltig.")
            else:
                image_count += 1

        # Char-Limit-Prüfung für Text-Slots
        if slot_def.type == "text" and slot_def.char_limit is not None:
            text = slot.get("text", "")
            if len(text) > slot_def.char_limit:
                errors.append(
                    f"Slot '{slot_id}': Text hat {len(text)} Zeichen (Limit: {slot_def.char_limit})."
                )

    if image_count > preset.image_count:
        errors.append(
            f"Zu viele Bilder: {image_count} (Preset '{page.template_id}' erlaubt {preset.image_count})."
        )
    if image_count < preset.image_count and image_count > 0:
        errors.append(
            f"Zu wenige Bilder: {image_count} (Preset '{page.template_id}' erwartet {preset.image_count})."
        )

    return errors


def enforce_fallback(page: PageDescription) -> PageDescription:
    """Repariert eine fehlerhafte Seite mit minimalen Eingriffen.

    Priorität: Preset erhalten → Text kürzen → Preset wechseln.
    """
    presets = load_all_presets()
    image_indices = [
        s["image_index"] for s in page.slots
        if s.get("image_index") is not None and s["image_index"] >= 0
    ]

    # Preset existiert nicht → passendes nach Bildanzahl wählen
    if page.template_id not in presets:
        page.template_id = get_any_preset(len(image_indices))

    preset = presets[page.template_id]
    slot_defs = {s.id: s for s in preset.slots}
    image_slot_ids = [s.id for s in preset.slots if s.type == "image"]

    repaired_slots = []

    # Bilder korrekten Image-Slots zuweisen
    for i, img_idx in enumerate(image_indices):
        if i >= len(image_slot_ids):
            break
        slot_data = {"slot_id": image_slot_ids[i], "image_index": img_idx}
        repaired_slots.append(slot_data)

    # Text-Slots aus Original übernehmen, dabei Char-Limit kürzen
    for slot in page.slots:
        sid = slot.get("slot_id", "")
        if sid in slot_defs:
            sd = slot_defs[sid]
            if sd.type == "text" and slot.get("text"):
                text = slot["text"]
                if sd.char_limit and len(text) > sd.char_limit:
                    text = text[:sd.char_limit]
                repaired_slots.append({"slot_id": sid, "text": text})

    return PageDescription(
        template_id=page.template_id,
        page_type="single",
        slots=repaired_slots,
    )


def check_variety(pages: List[PageDescription]) -> List[PageDescription]:
    """Stellt Abwechslung in der Preset-Sequenz sicher.

    Regeln:
    1. Seite 0 muss cover_hero sein
    2. Kein Preset mehr als 2× insgesamt
    3. Nicht 2× hintereinander gleiches Preset
    4. Max. 3 Seiten ohne Text hintereinander
    5. Nicht 3× hintereinander gleiche Bildanzahl
    6. Mindestens 5 verschiedene Presets im Buch
    """
    presets = load_all_presets()
    if not pages:
        return pages

    result = list(pages)

    # Regel 1: Cover erzwingen
    if result[0].template_id != "cover_hero":
        result[0] = _replace_preset(result[0], "cover_hero")

    # Regel 2 + 3: Kein Preset >2× insgesamt, kein Back-to-Back
    preset_counts = {}
    for i, page in enumerate(result):
        pid = page.template_id
        count = preset_counts.get(pid, 0) + 1
        if count > 2:
            replacement = _find_alternative_preset(pid, preset_counts)
            result[i] = _replace_preset(page, replacement)
            pid = replacement
            count = 1
        preset_counts[pid] = count

        # Back-to-Back-Check
        if i > 0 and pid == result[i - 1].template_id:
            replacement = _find_alternative_preset(pid, preset_counts)
            result[i] = _replace_preset(page, replacement)
            preset_counts[replacement] = preset_counts.get(replacement, 0) + 1

    # Regel 4: Max. 3 No-Text-Seiten hintereinander
    no_text_streak = 0
    for i, page in enumerate(result):
        preset = presets.get(page.template_id)
        if preset and not preset.has_text:
            no_text_streak += 1
            if no_text_streak > 3:
                text_presets = get_presets_by_image_count(preset.image_count, has_text=True)
                if text_presets:
                    result[i] = _replace_preset(page, text_presets[0])
                no_text_streak = 0
        else:
            no_text_streak = 0

    # Regel 5: Max. 2 Seiten gleiche Bildanzahl hintereinander
    same_count_streak = 0
    last_count = None
    for i, page in enumerate(result):
        preset = presets.get(page.template_id)
        if preset:
            if preset.image_count == last_count:
                same_count_streak += 1
                if same_count_streak > 2:
                    new_count = preset.image_count + 1 if preset.image_count < 4 else 1
                    replacement = get_any_preset(new_count)
                    result[i] = _replace_preset(page, replacement)
                    same_count_streak = 0
            else:
                same_count_streak = 1
                last_count = preset.image_count

    # Regel 6: Mindestens 5 verschiedene Presets
    unique = len({p.template_id for p in result})
    if unique < 5 and len(result) >= 5:
        used = {p.template_id for p in result}
        for i, page in enumerate(result):
            if unique >= 5:
                break
            preset = presets.get(page.template_id)
            if preset:
                alternatives = [
                    pid for pid in get_presets_by_image_count(preset.image_count)
                    if pid not in used
                ]
                if alternatives:
                    result[i] = _replace_preset(page, alternatives[0])
                    used.add(alternatives[0])
                    unique += 1

    return result


def _replace_preset(page: PageDescription, new_preset_id: str) -> PageDescription:
    """Ersetzt das Preset einer Seite, behält aber image_indices bei."""
    presets = load_all_presets()
    preset = presets.get(new_preset_id)
    if not preset:
        return page

    old_slots = page.slots
    new_slots = []

    image_indices = [
        s["image_index"] for s in old_slots
        if s.get("image_index") is not None and s["image_index"] >= 0
    ]

    image_slot_ids = [s.id for s in preset.slots if s.type == "image"]
    for i, img_idx in enumerate(image_indices):
        if i >= len(image_slot_ids):
            break
        new_slots.append({"slot_id": image_slot_ids[i], "image_index": img_idx})

    for slot in old_slots:
        sid = slot.get("slot_id", "")
        if sid in {s.id for s in preset.slots if s.type == "text"} and slot.get("text"):
            new_slots.append({"slot_id": sid, "text": slot["text"]})

    return PageDescription(
        template_id=new_preset_id,
        page_type="single",
        slots=new_slots,
    )


def _find_alternative_preset(current_id: str, used_counts: dict) -> str:
    """Findet alternatives Preset gleicher Bildanzahl, das noch nicht >2× verwendet wurde."""
    presets = load_all_presets()
    current = presets.get(current_id)
    if not current:
        return get_any_preset(1)

    candidates = get_presets_by_image_count(current.image_count)
    for pid in candidates:
        if pid != current_id and used_counts.get(pid, 0) < 2:
            return pid

    for pid in candidates:
        if pid != current_id:
            return pid

    return current_id


def validate_all_pages(pages: List[PageDescription]) -> tuple[List[PageDescription], List[str]]:
    """Validiert alle Seiten: Einzelseiten-Prüfung + Variety-Checks."""
    _presets = load_all_presets()
    validated = []
    warnings = []
    for i, page in enumerate(pages):
        errors = validate_page(page, _presets)
        if errors:
            warnings.append(f"Seite {i}: {', '.join(errors)}")
            validated.append(enforce_fallback(page))
        else:
            validated.append(page)

    validated = check_variety(validated)

    return validated, warnings
