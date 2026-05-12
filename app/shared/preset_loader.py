"""Generischer Preset-Loader (shared zwischen Photobuch und Kalender)."""
import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional
from pydantic import BaseModel, ValidationError


class PresetSlot(BaseModel):
    """Ein einzelner Slot in einem Preset."""
    id: str
    type: str
    css_area: str
    optional: bool = False
    priority: Optional[str] = None


class Preset(BaseModel):
    """Ein Layout-Preset aus dem Katalog."""
    id: str
    name: str
    image_count: int
    has_text: bool
    description: str
    css_class: str
    slots: list[PresetSlot]


def load_preset(preset_id: str, presets_dir: str) -> Preset:
    path = Path(presets_dir) / f"{preset_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Preset '{preset_id}' nicht gefunden unter {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    try:
        return Preset(**data)
    except ValidationError as e:
        raise ValidationError(f"Preset '{preset_id}' in {path} ist fehlerhaft: {e}") from e


@lru_cache(maxsize=16)
def _load_all_cached(presets_dir: str) -> dict[str, Preset]:
    presets = {}
    for path in sorted(Path(presets_dir).glob("*.json")):
        preset_id = path.stem
        presets[preset_id] = load_preset(preset_id, presets_dir)
    return presets


def load_all_presets(presets_dir: str) -> dict[str, Preset]:
    return _load_all_cached(presets_dir)
