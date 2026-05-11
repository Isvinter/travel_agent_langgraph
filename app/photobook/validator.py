"""Deterministischer Validator fuer LLM-Seitenbeschreibungen.

Prueft die LLM-Ausgabe auf Konsistenz VOR dem Rendering:
  - Slot-Konsistenz gegen Preset-Definition
  - Char-Limit-Overflow → Text kürzen
  - Variety-Checks (Cover, Back-to-Back, Text-Lücke, Bildanzahl-Monotonie, Gesamt-Variety)
"""

import logging
from typing import List
from app.state import PageDescription, PageSlot
from app.photobook.preset_loader import load_all_presets
from app.photobook.presets import get_any_preset, get_presets_by_image_count

logger = logging.getLogger(__name__)


def _truncate_text(text: str, limit: int) -> str:
    """Kürzt Text auf limit Zeichen, aber an der letzten Wortgrenze."""
    if len(text) <= limit:
        return text
    truncated = text[:limit]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        return truncated[:last_space]
    return truncated


def _text_placeholder(text_role: str) -> str:
    """Liefert einen Platzhalter-Text für leere Text-Slots."""
    placeholders = {
        "title": "Fotobuch",
        "caption": "Bildbeschreibung",
        "intro": "Einleitungstext",
    }
    return placeholders.get(text_role, "Text")


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
        slot_id = slot.slot_id
        if slot_id not in slot_defs:
            # "title" ist universell (page-header) und wird von enforce_fallback behandelt
            if slot_id == "title":
                continue
            # Image-Slots die nicht existieren → echter Fehler
            if slot.image_index is not None:
                errors.append(f"Slot '{slot_id}' existiert nicht im Preset '{page.template_id}'.")
                continue
            # Text-Slots an Presets ohne Text-Option → Fehler (kann nicht upgraden)
            if slot.text and not any(s.type == "text" for s in preset.slots):
                errors.append(f"Slot '{slot_id}' existiert nicht im Preset '{page.template_id}' (und kein Text-Upgrade möglich).")
            # Andere Text-Slots → enforce_fallback upgraded das Preset → keine Warnung
            continue

        slot_def = slot_defs[slot_id]

        if slot.image_index is not None:
            if slot.image_index < 0:
                errors.append(f"Slot '{slot_id}': image_index {slot.image_index} ist ungueltig.")
            else:
                image_count += 1

        # Char-Limit-Prüfung für Text-Slots
        if slot_def.type == "text" and slot_def.char_limit is not None:
            text = slot.text or ""
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


def _repair_slots(preset, old_slots: List[PageSlot]) -> List[dict]:
    """Repariert Slots für ein gegebenes Preset: Bilder zuweisen, Texte migrieren, Platzhalter füllen, Dedup."""
    image_indices = [
        s.image_index for s in old_slots
        if s.image_index is not None and s.image_index >= 0
    ]

    image_slot_ids = [s.id for s in preset.slots if s.type == "image"]
    repaired_slots: List[dict] = []

    for i, img_idx in enumerate(image_indices):
        if i >= len(image_slot_ids):
            break
        repaired_slots.append({"slot_id": image_slot_ids[i], "image_index": img_idx})

    slot_defs = {s.id: s for s in preset.slots}

    text_role_map = {}
    for sid, sd in slot_defs.items():
        if sd.type == "text":
            text_role_map[sd.text_role or sid] = sid

    for slot in old_slots:
        sid = slot.slot_id
        if sid == "title" and slot.text:
            repaired_slots.append({"slot_id": sid, "text": _truncate_text(slot.text, 60)})
        elif sid in slot_defs and slot_defs[sid].type == "text" and slot.text:
            sd = slot_defs[sid]
            text = slot.text
            if sd.char_limit and len(text) > sd.char_limit:
                text = _truncate_text(text, sd.char_limit)
            repaired_slots.append({"slot_id": sid, "text": text})
        elif slot.text and sid in text_role_map:
            matched_sid = text_role_map.get(sid)
            if not matched_sid and len(text_role_map) == 1:
                matched_sid = list(text_role_map.values())[0]
            if matched_sid:
                sd = slot_defs[matched_sid]
                text = slot.text
                if sd.char_limit and len(text) > sd.char_limit:
                    text = _truncate_text(text, sd.char_limit)
                repaired_slots.append({"slot_id": matched_sid, "text": text})
        elif slot.text:
            # Generischer Fallback: verwaister Text → erster Text-Slot im neuen Preset
            if text_role_map:
                new_sid = list(text_role_map.values())[0]
                sd = slot_defs[new_sid]
                text = slot.text
                if sd.char_limit and len(text) > sd.char_limit:
                    text = _truncate_text(text, sd.char_limit)
                logger.info("repair_slots fallback: %s:'%s...' → %s", sid, text[:30], new_sid)
                repaired_slots.append({"slot_id": new_sid, "text": text})

    for sid, sd in slot_defs.items():
        if sd.type == "text":
            already_filled = any(s.get("slot_id") == sid and s.get("text", "").strip() for s in repaired_slots)
            if not already_filled:
                placeholder = _text_placeholder(sd.text_role or "caption")
                repaired_slots.append({"slot_id": sid, "text": placeholder})

    has_title = any(s.get("slot_id") == "title" and s.get("text", "").strip() for s in repaired_slots)
    if not has_title:
        repaired_slots.append({"slot_id": "title", "text": "Fotobuch"})

    # Dedupliziere Slots: behalte letzten Eintrag pro slot_id (last wins)
    deduped_slots: List[dict] = []
    seen: set = set()
    for s in reversed(repaired_slots):
        sid = s.get("slot_id", "")
        if sid not in seen:
            seen.add(sid)
            deduped_slots.append(s)
    deduped_slots.reverse()

    return deduped_slots


def enforce_fallback(page: PageDescription) -> PageDescription:
    """Repariert eine fehlerhafte Seite mit minimalen Eingriffen.

    Priorität: Preset erhalten → Text kürzen → Preset wechseln (wenn LLM Text
    generiert hat, den das Preset nicht unterstützt).
    """
    presets = load_all_presets()
    image_indices = [
        s.image_index for s in page.slots
        if s.image_index is not None and s.image_index >= 0
    ]

    if page.template_id not in presets:
        page.template_id = get_any_preset(len(image_indices))

    preset = presets[page.template_id]

    llm_text_roles = set()
    for slot in page.slots:
        sid = slot.slot_id
        text = (slot.text or "").strip()
        if sid == "title" or not text:
            continue
        if sid in {s.id for s in preset.slots if s.type == "text"}:
            continue
        llm_text_roles.add(sid)

    if llm_text_roles and not preset.has_text and page.template_id != "cover_hero":
        text_presets = get_presets_by_image_count(preset.image_count, has_text=True)
        if text_presets:
            page.template_id = text_presets[0]
            preset = presets[page.template_id]

    deduped_slots = _repair_slots(preset, page.slots)
    return PageDescription(
        template_id=page.template_id,
        page_type="single",
        slots=[PageSlot(**s) for s in deduped_slots],
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

    # Regel 2 + 3: Kein Preset >2× insgesamt, cover_hero nur 1×, kein Back-to-Back
    preset_counts = {}
    for i, page in enumerate(result):
        pid = page.template_id
        count = preset_counts.get(pid, 0) + 1
        max_allowed = 1 if pid == "cover_hero" else 2
        if count > max_allowed:
            replacement = _find_alternative_preset(pid, preset_counts)
            result[i] = _replace_preset(result[i], replacement)
            pid = replacement
            count = 1
        preset_counts[pid] = count

        # Back-to-Back-Check (verwendet bereits ersetzte Seite result[i])
        if i > 0 and pid == result[i - 1].template_id:
            replacement = _find_alternative_preset(pid, preset_counts)
            result[i] = _replace_preset(result[i], replacement)
            # Alten Eintrag entfernen, neuen hochzählen
            preset_counts[pid] = preset_counts.get(pid, 1) - 1
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
                    # Neues Preset mit anderer Bildanzahl waehlen, aber NIE cover_hero
                    if preset.image_count >= 4:
                        new_count = 1
                    else:
                        new_count = preset.image_count + 1
                    # Filtere cover_hero aus, da es nur 1x auf Seite 0 sein darf
                    alternatives = get_presets_by_image_count(new_count)
                    non_cover = [pid for pid in alternatives if pid != "cover_hero"]
                    # Bevorzuge text-faehige Presets
                    text_alternatives = [pid for pid in non_cover if presets[pid].has_text]
                    if text_alternatives or non_cover:
                        replacement = (text_alternatives or non_cover)[0]
                    else:
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
            if i == 0:
                continue  # Cover-Seite nie ersetzen
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
    """Ersetzt das Preset einer Seite, behält aber image_indices und Text-Inhalte bei."""
    presets = load_all_presets()
    preset = presets.get(new_preset_id)
    if not preset:
        return page

    deduped_slots = _repair_slots(preset, page.slots)

    return PageDescription(
        template_id=new_preset_id,
        page_type="single",
        slots=[PageSlot(**s) for s in deduped_slots],
    )


def _find_alternative_preset(current_id: str, used_counts: dict) -> str:
    """Findet alternatives Preset gleicher Bildanzahl, das noch nicht >2× verwendet wurde.
    
    cover_hero darf NIE als Alternative für andere Presets dienen, da es nur 1×
    auf Seite 0 existieren darf. Beim Ersetzen von cover_hero werden text-fähige
    Alternativen bevorzugt, damit die Seite nicht wie eine zweite Titelseite aussieht.
    """
    presets = load_all_presets()
    current = presets.get(current_id)
    if not current:
        return get_any_preset(1)

    candidates = get_presets_by_image_count(current.image_count)
    # cover_hero nie als Alternative zurückgeben (darf nur auf Seite 0, 1×)
    candidates = [pid for pid in candidates if pid != "cover_hero"]
    if not candidates:
        return get_any_preset(current.image_count)

    if current_id == "cover_hero":
        # Beim Ersetzen von cover_hero: bevorzuge text-fähige Presets
        for pid in candidates:
            if presets[pid].has_text and used_counts.get(pid, 0) < 2:
                return pid
        for pid in candidates:
            if presets[pid].has_text:
                return pid

    # Standard: bevorzuge text-fähige Presets, dann count < 2
    for pid in candidates:
        if pid != current_id and presets[pid].has_text and used_counts.get(pid, 0) < 2:
            return pid
    for pid in candidates:
        if pid != current_id and presets[pid].has_text:
            return pid
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
        # enforce_fallback immer ausführen, damit alle Text-Slots befüllt sind
        validated.append(enforce_fallback(page))

    validated = check_variety(validated)

    return validated, warnings
