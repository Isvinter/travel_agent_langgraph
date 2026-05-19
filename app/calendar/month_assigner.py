"""Monats-Zuweisung: LLM weist Fotos den Kalender-Monaten und Slots zu."""
import logging
import os
import re
from datetime import datetime
from typing import Optional

from app.config import OLLAMA_BASE_URL
from app.services.ollama_client import call_ollama, strip_thinking_tokens
from app.state import ImageData
from app.calendar.layouts import CALENDAR_LAYOUT_SEQUENCE, MONTH_NAMES
from app.calendar.models import CalendarMonthPage, MonthSlot, CALENDAR_PRESET_CRITERIA
from app.shared.preset_loader import load_preset

logger = logging.getLogger(__name__)


def _parse_exif_date(timestamp: Optional[str]) -> Optional[datetime]:
    """Parst EXIF-Zeitstempel."""
    if not timestamp:
        return None
    for fmt in ["%Y:%m:%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
        try:
            return datetime.strptime(timestamp, fmt)
        except (ValueError, TypeError):
            continue
    try:
        return datetime.fromisoformat(timestamp)
    except (ValueError, TypeError):
        return None


def _build_assignment_prompt(
    selected_photos: list[tuple[str, str]],  # (filename, exif_date_or_empty)
    year: int,
    preset_criteria: str,
    custom_instructions: Optional[str] = None,
    orientations: Optional[list[str]] = None,
) -> str:
    if orientations and len(orientations) == len(selected_photos):
        photos_text = "\n".join(
            f"  {i}: {fname}"
            + (f" (EXIF: {date})" if date else "")
            + f" ({orientations[i].upper()})"
            for i, (fname, date) in enumerate(selected_photos)
        )
    else:
        photos_text = "\n".join(
            f"  {i}: {fname}" + (f" (EXIF: {date})" if date else "")
            for i, (fname, date) in enumerate(selected_photos)
        )

    presets_dir = os.path.join(os.path.dirname(__file__), "preset_data")
    layout_lines = []
    for i, (month_name, preset_id) in enumerate(CALENDAR_LAYOUT_SEQUENCE):
        preset = load_preset(preset_id, presets_dir)
        from app.calendar.layouts import SLOT_DIMENSIONS
        dims = SLOT_DIMENSIONS.get(preset_id, {})
        orientations_hint = ""
        if dims:
            wide_slots = [sid for sid, d in dims.items() if d.aspect_ratio > 1.5]
            tall_slots = [sid for sid, d in dims.items() if d.aspect_ratio < 0.67]
            hints = []
            if wide_slots:
                hints.append(f"Breitslots ({', '.join(wide_slots)}): Querformat bevorzugen")
            if tall_slots:
                hints.append(f"Hochslots ({', '.join(tall_slots)}): Hochformat bevorzugen")
            if hints:
                orientations_hint = " [" + "; ".join(hints) + "]"
        layout_lines.append(
            f"  {i}: {month_name} → {preset_id} ({preset.image_count} Bilder){orientations_hint}"
        )

    extra = f"\nZusätzliche Anweisungen: {custom_instructions}" if custom_instructions else ""

    return (
        f"Erstelle einen Fotokalender für das Jahr {year}.\n\n"
        f"Auswahlkriterien: {preset_criteria}{extra}\n\n"
        f"Verfügbare Fotos ({len(selected_photos)}):\n{photos_text}\n\n"
        "Seiten-Layouts (fix):\n" + "\n".join(layout_lines) +
        "\n\n"
        "Weise jedem Layout-Slot ein Foto zu (0-basierter Index). "
        "Saisonale Passung beachten: Schnee/Winter → Januar/Dezember, "
        "Blumen/Grün → April/Mai, Sonne/Strand → Juli/August, "
        "Herbstfarben → Oktober/November.\n\n"
        "Slot-Orientierungen beachten:\n"
        "- 'wide' Slots (Verhältnis > 1.5): bevorzuge Querformat-Fotos\n"
        "- 'tall' Slots (Verhältnis < 0.67): bevorzuge Hochformat-Fotos\n"
        "- 'square' Slots (0.67 ≤ Verhältnis ≤ 1.5): beide Formate ok\n\n"
        "Antworte im Format:\n"
        "# Deckblatt\n"
        "  cover_img: 5\n"
        "# Januar\n"
        "  img: 12\n"
        "# Februar\n"
        "  left: 3, right: 8\n"
        "... (pro Seite alle Slots auffüllen)\n\n"
        "Keine Erklärung, nur die Zuweisungen."
    )


def _parse_assignment_response(response: Optional[str]) -> dict[str, list[str]]:
    """Parst die LLM-Antwort in ein Dict: page_label → [Einträge]. Jeder Eintrag ist eine Zeile mit Slot-Zuweisungen."""
    if not response:
        return {}

    result = {}
    current_page = None
    for line in response.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        page_match = re.match(r"^#\s*(.+)", line)
        if page_match:
            current_page = page_match.group(1).strip()
            result[current_page] = []
            continue
        if current_page and ":" in line:
            result[current_page].append(line.strip())

    return result


def _fallback_assignment(
    selected_photos: list[ImageData],
    year: int,
    orientations: Optional[list[str]] = None,
) -> list[CalendarMonthPage]:
    """Fallback: Orientierungs-bewusste Zuordnung."""
    presets_dir = os.path.join(os.path.dirname(__file__), "preset_data")

    if orientations and len(orientations) == len(selected_photos):
        landscapes = [i for i, o in enumerate(orientations) if o == "landscape"]
        portraits = [i for i, o in enumerate(orientations) if o == "portrait"]
        squares = [i for i, o in enumerate(orientations) if o == "square"]
    else:
        landscapes = list(range(len(selected_photos)))
        portraits = []
        squares = []

    all_indices = landscapes + squares + portraits
    if not all_indices:
        all_indices = [0]

    from app.calendar.layouts import SLOT_DIMENSIONS

    pages = []
    landscape_ptr = 0
    portrait_ptr = 0
    square_ptr = 0

    def next_landscape():
        nonlocal landscape_ptr
        if landscapes:
            idx = landscapes[landscape_ptr % len(landscapes)]
            landscape_ptr += 1
            return idx
        if squares:
            nonlocal square_ptr
            idx = squares[square_ptr % len(squares)]
            square_ptr += 1
            return idx
        return all_indices[landscape_ptr % len(all_indices)]

    def next_portrait():
        nonlocal portrait_ptr
        if portraits:
            idx = portraits[portrait_ptr % len(portraits)]
            portrait_ptr += 1
            return idx
        if squares:
            nonlocal square_ptr
            idx = squares[square_ptr % len(squares)]
            square_ptr += 1
            return idx
        return all_indices[portrait_ptr % len(all_indices)]

    def next_square():
        nonlocal square_ptr
        if squares:
            idx = squares[square_ptr % len(squares)]
            square_ptr += 1
            return idx
        return all_indices[square_ptr % len(all_indices)]

    for month, preset_id in CALENDAR_LAYOUT_SEQUENCE:
        preset = load_preset(preset_id, presets_dir)
        dims = SLOT_DIMENSIONS.get(preset_id, {})
        slots = []
        for slot_def in preset.slots:
            if slot_def.type != "image":
                continue
            slot_dims = dims.get(slot_def.id)
            if slot_dims:
                if slot_dims.aspect_ratio > 1.5:
                    img_index = next_landscape()
                elif slot_dims.aspect_ratio < 0.67:
                    img_index = next_portrait()
                else:
                    img_index = next_square()
            else:
                img_index = all_indices[len(slots) % len(all_indices)]

            slots.append(MonthSlot(slot_id=slot_def.id, image_index=img_index))

        month_num = 0 if month == "Deckblatt" else MONTH_NAMES.index(month) + 1
        pages.append(CalendarMonthPage(
            month=month_num,
            month_name=month,
            preset_id=preset_id,
            slots=slots,
        ))

    return pages


def assign_photos_to_months(
    selected_photos: list[ImageData],
    year: int,
    preset: str = "mixed",
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
    custom_instructions: Optional[str] = None,
    orientations: Optional[list[str]] = None,
) -> list[CalendarMonthPage]:
    """LLM-basierte Zuordnung von Fotos zu Kalender-Monaten und Slots."""
    if not selected_photos:
        logger.warning("Keine Fotos zur Auswahl, verwende Fallback ohne Bilder")
        return _fallback_assignment([], year, orientations=orientations)

    criteria = CALENDAR_PRESET_CRITERIA.get(preset, CALENDAR_PRESET_CRITERIA["mixed"])

    photo_list: list[tuple[str, str]] = []
    for img in selected_photos:
        fname = os.path.basename(img.path)
        date_str = ""
        dt = _parse_exif_date(img.timestamp)
        if dt:
            date_str = dt.strftime("%Y-%m-%d")
        photo_list.append((fname, date_str))

    prompt = _build_assignment_prompt(
        photo_list, year, criteria, custom_instructions, orientations=orientations
    )

    response = call_ollama(
        prompt,
        model=model,
        base_url=base_url,
        temperature=0.0,
        top_p=0.1,
        num_predict=4096,  # /no_think reduziert Thinking, genug für 35 Slot-Zuweisungen
        timeout=120,
        disable_thinking=True,
    )

    if response:
        content = strip_thinking_tokens(response)
        parsed = _parse_assignment_response(content)

        if parsed and len(parsed) >= 10:
            pages = _build_pages_from_parsed(parsed, selected_photos)
            if len(pages) == 13 and all(len(p.slots) > 0 for p in pages):
                return pages
            logger.info("LLM-Zuweisung unvollständig (%d Seiten), verwende Fallback", len(pages))

    logger.info("LLM-Zuweisung fehlgeschlagen, verwende Fallback")
    return _fallback_assignment(selected_photos, year, orientations=orientations)


def _build_pages_from_parsed(
    parsed: dict[str, list[str]],
    selected_photos: list[ImageData],
) -> list[CalendarMonthPage]:
    """Baut CalendarMonthPage-Objekte aus geparster LLM-Antwort."""
    pages = []
    for month, preset_id in CALENDAR_LAYOUT_SEQUENCE:
        page_entries = parsed.get(month, [])
        slots = []
        for entry in page_entries:
            slot_pairs = re.findall(r'(\w+)\s*:\s*(\d+)', entry)
            for slot_id, idx_str in slot_pairs:
                try:
                    img_idx = int(idx_str)
                    if 0 <= img_idx < len(selected_photos):
                        slots.append(MonthSlot(slot_id=slot_id, image_index=img_idx))
                except ValueError:
                    continue

        month_num = 0 if month == "Deckblatt" else MONTH_NAMES.index(month) + 1
        pages.append(CalendarMonthPage(
            month=month_num,
            month_name=month,
            preset_id=preset_id,
            slots=slots,
        ))

    return pages
