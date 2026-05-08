"""HTML-Assembler fuer Fotobuch-Seiten.

Nimmt PageDescription-Objekte und erzeugt ein vollstaendiges HTML-Dokument
mit CSS Grid Layouts aus den Preset-Definitionen.
"""

import html
import os
from typing import List
from app.state import PageDescription, ImageData
from app.photobook.preset_loader import load_preset

_STYLES_PATH = os.path.join(os.path.dirname(__file__), "styles.css")


def _read_styles() -> str:
    with open(_STYLES_PATH, "r", encoding="utf-8") as f:
        return f.read()


PHOTOBOOK_HEADER = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fotobuch</title>
<style>
{_read_styles()}
</style>
</head>
<body>
"""

PHOTOBOOK_FOOTER = """
</body>
</html>
"""


def render_photobook(pages: List[PageDescription], images: List[ImageData]) -> str:
    """Erzeugt ein vollstaendiges HTML-Dokument aus Seitenbeschreibungen.

    Jede Seite hat einen page-header (Titel) und page-content (Preset-Layout).
    """
    html_parts = [PHOTOBOOK_HEADER]

    for page_idx, page in enumerate(pages):
        preset = load_preset(page.template_id)
        css_class = preset.css_class
        page_title = _extract_title(page, page_idx)

        # Cover-Seite: Vollbild mit Titel-Overlay, kein page-header
        if page.template_id == "cover_hero":
            html_parts.append(_render_cover_page(page, page_title, images))
            continue

        # Normale Seite: page-header + page-content
        html_parts.append('<div class="photobook-page page-single">')
        html_parts.append('<div class="page-header">')
        html_parts.append(f'<div class="page-title">{html.escape(page_title)}</div>')
        html_parts.append('</div>')

        html_parts.append(f'<div class="page-content {css_class}">')

        slot_defs = {s.id: s for s in preset.slots}

        for slot_data in page.slots:
            slot_id = slot_data.get("slot_id", "")
            slot_def = slot_defs.get(slot_id)
            if not slot_def:
                continue

            if slot_def.text_role == "title":
                continue

            area_style = f'style="grid-area: {slot_def.css_area}"'

            if slot_def.type == "image" and slot_data.get("image_index") is not None:
                idx = slot_data["image_index"]
                if 0 <= idx < len(images):
                    img_path = _normalize_path(images[idx].path)
                    html_parts.append(
                        f'<img class="slot-image" {area_style} '
                        f'src="{img_path}" alt="Foto {idx + 1}">'
                    )
                else:
                    html_parts.append(
                        f'<div class="slot-image slot-placeholder" {area_style}>'
                        f'Bild {slot_data["image_index"]} nicht gefunden</div>'
                    )

            elif slot_def.type == "text":
                text = html.escape(slot_data.get("text", ""))
                font_size = slot_def.font_size or "11pt"
                style = f'style="grid-area: {slot_def.css_area}; font-size: {font_size}"'

                if slot_def.text_role == "title":
                    css_cls = "slot-title"
                elif slot_def.text_role == "caption":
                    css_cls = "slot-caption"
                else:
                    css_cls = "slot-text"

                html_parts.append(
                    f'<div class="{css_cls}" {style}>{text}</div>'
                )

        html_parts.append("</div>")  # page-content
        html_parts.append("</div>")  # photobook-page

    html_parts.append(PHOTOBOOK_FOOTER)
    return "\n".join(html_parts)


def _render_cover_page(page: PageDescription, title: str, images: List[ImageData]) -> str:
    """Rendert die Cover-Seite als Vollbild mit Titel-Overlay."""
    preset = load_preset(page.template_id)
    parts = ['<div class="photobook-page page-single cover-page">']

    # Cover-Bild
    for slot_data in page.slots:
        slot_id = slot_data.get("slot_id", "")
        if slot_id == "title":
            continue
        idx = slot_data.get("image_index", -1)
        if 0 <= idx < len(images):
            img_path = _normalize_path(images[idx].path)
            parts.append(
                f'<img class="cover-image" '
                f'src="{img_path}" alt="Cover">'
            )

    # Titel-Overlay
    parts.append('<div class="cover-overlay">')
    parts.append('<div class="cover-book-title">Fotobuch</div>')
    parts.append(f'<div class="cover-title">{html.escape(title)}</div>')
    parts.append('</div>')

    parts.append('</div>')
    return "\n".join(parts)


def _extract_title(page: PageDescription, page_idx: int) -> str:
    """Extrahiert den Seitentitel aus den Slots oder generiert Fallback."""
    for slot in page.slots:
        if slot.get("slot_id") == "title" and slot.get("text", "").strip():
            return slot["text"]
    return f"Seite {page_idx + 1}"


def _normalize_path(path: str) -> str:
    """Konvertiert Pfade zu file:/// URIs fuer Headless Chrome."""
    abs_path = os.path.abspath(path)
    return f"file://{abs_path}"
