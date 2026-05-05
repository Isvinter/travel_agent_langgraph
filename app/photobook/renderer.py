"""HTML-Assembler fuer Fotobuch-Seiten.

Nimmt PageDescription-Objekte und erzeugt ein vollstaendiges HTML-Dokument
mit CSS Grid Layouts, das via Headless Chrome als PDF gedruckt werden kann.
"""

import html
import os
from typing import List
from app.state import PageDescription, ImageData
from app.photobook.template_loader import load_template

_STYLES_PATH = os.path.join(os.path.dirname(__file__), "styles.css")


def _read_styles() -> str:
    with open(_STYLES_PATH, "r", encoding="utf-8") as f:
        return f.read()


PHOTOBOOK_HEADER = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fotobuch</title>
<style>
""" + _read_styles() + """
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

    Args:
        pages: Liste von PageDescription (vom LLM)
        images: Liste aller ImageData-Objekte

    Returns:
        Vollstaendiges HTML-Dokument als String
    """
    html_parts = [PHOTOBOOK_HEADER]

    for page in pages:
        template = load_template(page.template_id)
        css_class = template.css_class
        page_css = f"page-{page.page_type}"
        html_parts.append(f'<div class="photobook-page {css_class} {page_css}">')

        slot_defs = {s.id: s for s in template.slots}

        for slot_data in page.slots:
            slot_id = slot_data.get("slot_id", "")
            slot_def = slot_defs.get(slot_id)
            if not slot_def:
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
                # Caption im dedizierten Caption-Slot des Templates rendern
                caption = html.escape(slot_data.get("caption", ""))
                if caption:
                    caption_slot_def = next((s for s in template.slots if s.type == "caption"), None)
                    if caption_slot_def:
                        caption_area = f'style="grid-area: {caption_slot_def.css_area}"'
                    else:
                        caption_area = area_style  # Fallback: Template hat keinen Caption-Slot
                    html_parts.append(
                        f'<div class="slot-caption" {caption_area}>{caption}</div>'
                    )

            elif slot_def.type == "text":
                text = html.escape(slot_data.get("text", ""))
                html_parts.append(
                    f'<div class="slot-text" {area_style}>{text}</div>'
                )

            elif slot_def.type == "caption":
                caption = html.escape(slot_data.get("caption", ""))
                if caption:
                    html_parts.append(
                        f'<div class="slot-caption" {area_style}>{caption}</div>'
                    )

        html_parts.append("</div>")

    html_parts.append(PHOTOBOOK_FOOTER)
    return "\n".join(html_parts)


def _normalize_path(path: str) -> str:
    """Konvertiert Pfade zu file:/// URIs fuer Headless Chrome."""
    abs_path = os.path.abspath(path)
    return f"file://{abs_path}"
