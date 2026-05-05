"""Template-Loader — lädt JSON-Templates und parst sie in Pydantic-Modelle."""

import json
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

_TEMPLATES_DIR = Path(__file__).parent / "templates"


class SlotDefinition(BaseModel):
    """Ein einzelner Slot in einem Template."""

    id: str
    type: str  # "image" | "text" | "caption"
    priority: Optional[str] = None  # "primary" | "secondary" | None
    css_area: str
    optional: bool = False


class PhotobookTemplate(BaseModel):
    """Ein Layout-Template aus dem Katalog."""

    id: str
    name: str
    category: str
    description: str
    page_type: str  # "single" | "spread"
    min_images: int
    max_images: int
    has_text: bool = False
    supports_captions: bool = False
    css_class: str
    slots: List[SlotDefinition]


def load_template(template_id: str) -> PhotobookTemplate:
    """Lädt ein einzelnes Template aus dem Katalog."""
    path = _TEMPLATES_DIR / f"{template_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Template '{template_id}' nicht gefunden unter {path}"
        )
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return PhotobookTemplate(**data)


def load_all_templates() -> Dict[str, PhotobookTemplate]:
    """Lädt alle Templates aus dem Katalog."""
    templates = {}
    for path in sorted(_TEMPLATES_DIR.glob("*.json")):
        template_id = path.stem
        templates[template_id] = load_template(template_id)
    return templates


def get_template_summary_for_llm() -> str:
    """Erzeugt eine Kurzübersicht aller Templates für den LLM-Prompt."""
    lines = []
    for tid, tmpl in load_all_templates().items():
        slot_info = ", ".join(
            f"{s.id}({s.type},{s.priority or 'normal'})" for s in tmpl.slots
        )
        lines.append(
            f"- {tid} [{tmpl.category}/{tmpl.page_type}] "
            f"({tmpl.min_images}-{tmpl.max_images} Bilder): {slot_info}"
        )
    return "\n".join(lines)
