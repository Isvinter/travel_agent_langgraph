"""LLM Pass 2: Slot-Zuweisung + Text innerhalb von Preset-Constraints."""

import json
import re
from typing import Any, Dict, List, Optional
import requests
from app.config import OLLAMA_BASE_URL
from app.state import ImageData, PageDescription
from app.photobook.preset_loader import load_all_presets
from app.photobook.presets import get_constraint_summary, get_any_preset
from app.utils.image_utils import encode_image_base64


def _build_generate_prompt(pages_plan, gpx_stats_d, notes):
    presets = load_all_presets()
    preset_summary = []
    for pid, p in presets.items():
        slot_info = ", ".join(
            f"{s.id}({s.type},{s.text_role or s.priority or '-'})" for s in p.slots
        )
        preset_summary.append(f"  {pid} [{p.image_count} Bilder, Text={'ja' if p.has_text else 'nein'}]: {slot_info}")
    catalog = "\n".join(preset_summary)

    constraints = get_constraint_summary()

    plan_text = json.dumps(pages_plan, indent=2, ensure_ascii=False)
    gpx_text = ""
    if gpx_stats_d:
        dist = gpx_stats_d.get("total_distance_m", 0) / 1000
        elev = gpx_stats_d.get("elevation_gain_m", 0)
        gpx_text = f"\nTOUR: {dist:.1f} km, {elev:.0f}m Hoehenmeter."
    notes_text = f"\nTOUR-NOTIZEN: {notes}" if notes else ""

    return f"""Du befuellst die Slots der gewaehlten Presets mit Bildern und Text.

SEITENPLAN (preset_id pro Seite):
{plan_text}

PRESET-SLOTS:
{catalog}
{gpx_text}{notes_text}

{constraints}

AUFGABE PRO SEITE:
1. Weise jedem Image-Slot ein Bild zu (image_index aus dem Plan)
2. Generiere Text NUR wenn das Preset Text-Slots hat
3. Text MUSS innerhalb des Zeichenlimits bleiben (Validator kuerzt sonst)
4. Textrollen: title (stimmungsvoller Seitentitel), caption (Bildunterschrift), intro (Einleitung)

ANTWORTE NUR mit JSON-Array:
[{{"preset_id": "cover_hero", "slots": [{{"slot_id": "main", "image_index": 3}}, {{"slot_id": "title", "text": "Gipfelstuermer"}}]}}]"""


def generate_photobook_pages(
    plan: Dict[str, Any],
    images: List[ImageData],
    gpx_stats: Optional[Dict[str, Any]],
    notes: Optional[str],
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
) -> List[PageDescription]:
    pages_plan = plan.get("pages", [])
    if not pages_plan:
        return []
    prompt = _build_generate_prompt(pages_plan, gpx_stats, notes)

    # Bilder als Base64 encodieren
    encoded_images = []
    for img in images:
        b64 = encode_image_base64(img.path)
        if b64:
            encoded_images.append(b64)

    try:
        payload = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": prompt,
                "images": encoded_images,
            }],
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 8192},
            "keep_alive": "10m",
        }
        resp = requests.post(
            f"{base_url.rstrip('/')}/api/chat",
            json=payload,
            timeout=300,
        )
        if resp.status_code == 200:
            content = resp.json().get("message", {}).get("content", "")
            array_match = re.search(r'\[.*\]', content, re.DOTALL)
            if array_match:
                pages_data = json.loads(array_match.group())
                result = []
                for pd in pages_data:
                    valid_slots = []
                    for slot in pd.get("slots", []):
                        idx = slot.get("image_index", -1)
                        if 0 <= idx < len(images):
                            valid_slots.append(slot)
                        else:
                            # Entferne image_index wenn ungültig, behalte text
                            cleansed = {k: v for k, v in slot.items() if k != "image_index"}
                            if cleansed.get("text") or cleansed.get("slot_id"):
                                valid_slots.append(cleansed)
                    page = PageDescription(
                        template_id=pd.get("preset_id", "quad_grid"),
                        page_type="single",
                        slots=valid_slots,
                    )
                    result.append(page)
                if result:
                    return result
    except Exception as e:
        print(f"⚠️ Pass 2 (Generierung) fehlgeschlagen: {e}")

    # Fallback: verwende das im Plan gewählte Preset mit einfacher Slot-Zuweisung
    all_presets = load_all_presets()
    fallback = []
    for plan_page in pages_plan:
        preset_id = plan_page.get("preset_id", "quad_grid")
        preset = all_presets.get(preset_id)
        if preset is None:
            # Fallback: nächstes Preset mit passender Bildanzahl
            count = len(plan_page.get("image_indices", []))
            preset_id = get_any_preset(count)
            preset = all_presets.get(preset_id, all_presets["quad_grid"])

        indices = plan_page.get("image_indices", [])
        image_slots = [s.id for s in preset.slots if s.type == "image"]
        slots = []
        for sid, idx in zip(image_slots, indices):
            slots.append({"slot_id": sid, "image_index": idx})
        fallback.append(PageDescription(
            template_id=preset_id,
            page_type="single",
            slots=slots,
        ))
    return fallback
