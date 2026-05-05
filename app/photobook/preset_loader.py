"""Preset-Loader — lädt JSON-Presets und parst sie in Pydantic-Modelle."""
import json
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

_PRESETS_DIR = Path(__file__).parent / "preset_data"


class PresetSlot(BaseModel):
    """Ein einzelner Slot in einem Preset."""
    id: str
    type: str                          # "image" | "text"
    priority: Optional[str] = None     # "primary" | "secondary" | None
    css_area: str
    optional: bool = False
    char_limit: Optional[int] = None   # Zeichenlimit (nur für type="text")
    font_size: Optional[str] = None    # CSS font-size (nur für type="text")
    text_role: Optional[str] = None    # "title" | "caption" | "intro" (nur für type="text")


class Preset(BaseModel):
    """Ein Layout-Preset aus dem Katalog."""
    id: str
    name: str
    image_count: int
    has_text: bool
    description: str
    css_class: str
    slots: List[PresetSlot]


def load_preset(preset_id: str) -> Preset:
    """Lädt ein einzelnes Preset aus dem Katalog."""
    path = _PRESETS_DIR / f"{preset_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Preset '{preset_id}' nicht gefunden unter {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Preset(**data)


def load_all_presets() -> Dict[str, Preset]:
    """Lädt alle Presets aus dem Katalog."""
    presets = {}
    for path in sorted(_PRESETS_DIR.glob("*.json")):
        preset_id = path.stem
        presets[preset_id] = load_preset(preset_id)
    return presets


def get_preset_catalog_for_llm() -> str:
    """Erzeugt Kurzübersicht aller Presets für Pass-1-Prompt (nur ID, Bildanzahl, Text)."""
    lines = []
    for pid, p in load_all_presets().items():
        lines.append(f"  {pid}: {p.image_count} Bilder, Text={'ja' if p.has_text else 'nein'}")
    return "\n".join(lines)


def get_constraint_table_for_llm() -> str:
    """Erzeugt Text-Constraint-Tabelle für Pass-2-Prompt."""
    constraints: Dict[str, tuple[int, str]] = {}
    for preset in load_all_presets().values():
        for slot in preset.slots:
            if slot.type == "text" and slot.text_role:
                # None-Werte überspringen (sollte nie vorkommen, aber defensiv)
                if slot.char_limit is None or slot.font_size is None:
                    continue
                key = slot.text_role
                if key not in constraints:
                    constraints[key] = (slot.char_limit, slot.font_size)
    lines = ["TEXT-CONSTRAINTS:"]
    for role, (limit, size) in sorted(constraints.items()):
        lines.append(f"  {role}: max. {limit} Zeichen, Schriftgröße {size}")
    return "\n".join(lines)
