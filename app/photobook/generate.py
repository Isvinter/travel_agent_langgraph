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
    # Nur die tatsächlich im Plan verwendeten Presets laden
    all_presets = load_all_presets()
    used_preset_ids = set()
    for pp in pages_plan:
        pid = pp.get("preset_id", "")
        if pid:
            used_preset_ids.add(pid)

    # Nur relevante Presets anzeigen
    preset_summary = []
    for pid in sorted(used_preset_ids):
        p = all_presets.get(pid)
        if p:
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

    # Bilde Text-Slot-Pflicht basierend auf den verwendeten Presets
    text_required = any(all_presets.get(pid) and all_presets[pid].has_text for pid in used_preset_ids)

    return f"""Du befuellst die Slots der gewaehlten Presets mit Bildern und Text.

SEITENPLAN (preset_id pro Seite):
{plan_text}

VERWENDETE PRESETS (nur diese sind relevant):
{catalog}
{gpx_text}{notes_text}

{constraints}

{"TEXT IST PFLICHT: Hat ein Preset Text-Slots, MUSST du diese befuellen. Lass KEINEN Text-Slot leer. Betrachte die Bilder und beschreibe, was du siehst." if text_required else ""}

AUFGABE PRO SEITE:
1. Weise jedem Image-Slot ein Bild zu (image_index aus dem Plan).
2. Text-Rollen: title (stimmungsvoller Titel, 60 Z.), caption (Bildbeschreibung, 170 Z.), intro (Einleitung, 400 Z.).
3. Generiere kurze, passende Texte — innerhalb der Zeichenlimits.
4. JEDE Seite MUSS einen title-Slot haben: {{"slot_id": "title", "text": "Einzeiliger Seitentitel"}}

BEISPIELE:
- cover_hero: [{{"preset_id": "cover_hero", "slots": [{{"slot_id": "title", "text": "Aufbruch im Morgengrauen"}}, {{"slot_id": "main", "image_index": 0}}]}}]
- single_text_below: [{{"preset_id": "single_text_below", "slots": [{{"slot_id": "title", "text": "Alpenwiese"}}, {{"slot_id": "main", "image_index": 1}}, {{"slot_id": "caption", "text": "Weitblick ueber das Tal"}}]}}]
- double_stacked (KEIN Text): [{{"preset_id": "double_stacked", "slots": [{{"slot_id": "title", "text": "Aufstieg"}}, {{"slot_id": "top", "image_index": 3}}, {{"slot_id": "bottom", "image_index": 4}}]}}]
- image_text_split: [{{"preset_id": "image_text_split", "slots": [{{"slot_id": "title", "text": "Kapitel 1"}}, {{"slot_id": "image", "image_index": 2}}, {{"slot_id": "text", "text": "Nach drei Stunden erreichten wir die Baumgrenze."}}]}}]

ANTWORTE NUR mit JSON-Array:"""


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
                # Debug: zeige wie viele Text-Slots das LLM gefuellt hat
                text_slots = sum(1 for pd in pages_data for s in pd.get("slots", []) if "text" in s)
                print(f"  → LLM hat {text_slots} Text-Slots gefüllt (von {len(pages_data)} Seiten)")
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
        # Universeller Title-Slot fuer den Fallback
        slots.append({"slot_id": "title", "text": "Fotobuch"})
        fallback.append(PageDescription(
            template_id=preset_id,
            page_type="single",
            slots=slots,
        ))
    return fallback
