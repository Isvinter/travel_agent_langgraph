"""Preset-Loader — lädt JSON-Presets und parst sie in Pydantic-Modelle."""
import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, ValidationError

_PRESETS_DIR = Path(__file__).parent / "preset_data"


class PresetSlot(BaseModel):
    """Ein einzelner Slot in einem Preset."""
    id: str
    type: str                          # "image" | "text"
    priority: Optional[str] = None     # "primary" | "secondary" | None
    css_area: str
    optional: bool = False
    char_limit: Optional[int] = None   # Zeichenlimit (nur für type="text")
    char_min: Optional[int] = None     # Mindest-Zeichenzahl (nur für type="text")
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
    try:
        return Preset(**data)
    except ValidationError as e:
        raise ValidationError(f"Preset '{preset_id}' in {path} ist fehlerhaft: {e}") from e


@lru_cache(maxsize=1)
def load_all_presets() -> Dict[str, Preset]:
    """Lädt alle Presets aus dem Katalog."""
    presets = {}
    for path in sorted(_PRESETS_DIR.glob("*.json")):
        preset_id = path.stem
        presets[preset_id] = load_preset(preset_id)
    return presets

