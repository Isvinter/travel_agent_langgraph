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
) -> str:
    photos_text = "\n".join(
        f"  {i}: {fname}" + (f" (EXIF: {date})" if date else "")
        for i, (fname, date) in enumerate(selected_photos)
    )

    presets_dir = os.path.join(os.path.dirname(__file__), "preset_data")
    layout_lines = []
    for i, (month_name, preset_id) in enumerate(CALENDAR_LAYOUT_SEQUENCE):
        preset = load_preset(preset_id, presets_dir)
        layout_lines.append(f"  {i}: {month_name} → {preset_id} ({preset.image_count} Bilder)")

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
) -> list[CalendarMonthPage]:
    """Fallback: Chronologische/EXIF-basierte Zuordnung."""
    presets_dir = os.path.join(os.path.dirname(__file__), "preset_data")

    dated = []
    undated = []
    for i, img in enumerate(selected_photos):
        dt = _parse_exif_date(img.timestamp)
        if dt:
            dated.append((i, dt))
        else:
            undated.append(i)

    dated.sort(key=lambda x: x[1])
    sorted_indices = [i for i, _ in dated] + undated

    pages = []
    photo_idx = 0

    for month, preset_id in CALENDAR_LAYOUT_SEQUENCE:
        preset = load_preset(preset_id, presets_dir)
        slots = []
        for slot in preset.slots:
            if slot.type == "image":
                img_index = sorted_indices[photo_idx % len(sorted_indices)] if sorted_indices else 0
                slots.append(MonthSlot(slot_id=slot.id, image_index=img_index))
                photo_idx += 1
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
) -> list[CalendarMonthPage]:
    """LLM-basierte Zuordnung von Fotos zu Kalender-Monaten und Slots."""
    if not selected_photos:
        logger.warning("Keine Fotos zur Auswahl, verwende Fallback ohne Bilder")
        return _fallback_assignment([], year)

    criteria = CALENDAR_PRESET_CRITERIA.get(preset, CALENDAR_PRESET_CRITERIA["mixed"])

    photo_list: list[tuple[str, str]] = []
    for img in selected_photos:
        fname = os.path.basename(img.path)
        date_str = ""
        dt = _parse_exif_date(img.timestamp)
        if dt:
            date_str = dt.strftime("%Y-%m-%d")
        photo_list.append((fname, date_str))

    prompt = _build_assignment_prompt(photo_list, year, criteria, custom_instructions)

    response = call_ollama(
        prompt,
        model=model,
        base_url=base_url,
        temperature=0.0,
        top_p=0.1,
        num_predict=16384,
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
    return _fallback_assignment(selected_photos, year)


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
