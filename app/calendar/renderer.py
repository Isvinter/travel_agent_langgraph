"""HTML-Assembler für den Fotokalender."""
import html as html_mod
import os
import urllib.parse
from typing import List

from app.calendar.models import CalendarMonthPage
from app.calendar.day_grid import generate_day_grid
from app.shared.preset_loader import load_preset

_STYLES_PATH = os.path.join(os.path.dirname(__file__), "styles.css")


def _read_styles() -> str:
    with open(_STYLES_PATH, "r", encoding="utf-8") as f:
        return f.read()


CALENDAR_HEADER = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fotokalender</title>
<style>
{_read_styles()}
</style>
</head>
<body>
"""

CALENDAR_FOOTER = """\n</body>\n</html>"""


def _normalize_path(path: str) -> str:
    abs_path = os.path.abspath(path)
    return urllib.parse.urljoin("file://", urllib.parse.quote(abs_path))


def render_calendar(
    pages: List[CalendarMonthPage],
    year: int,
    image_paths: List[str],
) -> str:
    """Erzeugt ein vollständiges HTML-Dokument für den Kalender."""
    presets_dir = os.path.join(os.path.dirname(__file__), "preset_data")
    parts = [CALENDAR_HEADER]

    for page in pages:
        if page.month == 0:
            parts.append(_render_cover(page, year, image_paths, presets_dir))
        else:
            parts.append(_render_month_page(page, year, image_paths, presets_dir))

    parts.append(CALENDAR_FOOTER)
    return "\n".join(parts)


def _render_cover(
    page: CalendarMonthPage,
    year: int,
    image_paths: List[str],
    presets_dir: str,
) -> str:
    preset = load_preset(page.preset_id, presets_dir)
    parts = ['<div class="calendar-page cover-page">']

    for slot_data in page.slots:
        slot_def = next((s for s in preset.slots if s.id == slot_data.slot_id), None)
        if slot_def and slot_def.type == "image":
            idx = slot_data.image_index
            if 0 <= idx < len(image_paths):
                img_path = _normalize_path(image_paths[idx])
                parts.append(
                    f'<img class="cover-image" '
                    f'src="{html_mod.escape(img_path)}" alt="Cover">'
                )

    parts.append('<div class="cover-overlay">')
    parts.append(f'<div class="cover-year">{html_mod.escape(str(year))}</div>')
    parts.append('</div>')
    parts.append('</div>')

    return "\n".join(parts)


def _render_month_page(
    page: CalendarMonthPage,
    year: int,
    image_paths: List[str],
    presets_dir: str,
) -> str:
    preset = load_preset(page.preset_id, presets_dir)
    css_class = preset.css_class

    parts = ['<div class="calendar-page">']

    # Monatskopf
    parts.append('<div class="month-header">')
    parts.append(f'<span class="month-name">{html_mod.escape(page.month_name)}</span>')
    parts.append(f'<span class="year-label">{html_mod.escape(str(year))}</span>')
    parts.append('</div>')

    # Bildbereich
    parts.append(f'<div class="image-area {css_class}">')

    slot_defs = {s.id: s for s in preset.slots}
    for slot_data in page.slots:
        slot_def = slot_defs.get(slot_data.slot_id)
        if not slot_def or slot_def.type != "image":
            continue

        area_style = f'style="grid-area: {slot_def.css_area}"'
        idx = slot_data.image_index
        if 0 <= idx < len(image_paths):
            img_path = _normalize_path(image_paths[idx])
            parts.append(
                f'<img class="slot-image" {area_style} '
                f'src="{html_mod.escape(img_path)}" alt="Foto">'
            )
        else:
            parts.append(
                f'<div class="slot-placeholder" {area_style}>'
                f'Bild nicht verfügbar</div>'
            )

    parts.append('</div>')  # image-area

    # Tagesraster
    parts.append(generate_day_grid(page.month, year))

    parts.append('</div>')  # calendar-page

    return "\n".join(parts)
