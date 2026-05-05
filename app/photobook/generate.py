"""LLM Pass 2: Template-Auswahl + Slot-Zuweisung + Caption-Generierung."""

import json
import re
from typing import Any, Dict, List, Optional
import requests
from app.config import OLLAMA_BASE_URL
from app.state import ImageData, PageDescription
from app.photobook.template_loader import load_all_templates
from app.utils.image_utils import encode_image_base64


def _build_generate_prompt(pages_plan, gpx_stats_d, notes):
    templates_summary = []
    for tid, tmpl in load_all_templates().items():
        slot_info = ", ".join(f"{s.id}({s.type},{s.priority or 'normal'})" for s in tmpl.slots)
        templates_summary.append(f"  {tid} [{tmpl.category}/{tmpl.page_type}, {tmpl.min_images}-{tmpl.max_images} Bilder]: {slot_info}")
    catalog = "\n".join(templates_summary)
    plan_text = json.dumps(pages_plan, indent=2, ensure_ascii=False)
    gpx_text = ""
    if gpx_stats_d:
        dist = gpx_stats_d.get("total_distance_m", 0) / 1000
        elev = gpx_stats_d.get("elevation_gain_m", 0)
        gpx_text = f"\nTOUR: {dist:.1f} km, {elev:.0f}m Hoehenmeter."
    notes_text = f"\nTOUR-NOTIZEN: {notes}" if notes else ""
    return f"""Du waehlst fuer jede geplante Seite das konkrete Template aus.

SEITENPLAN:
{plan_text}

TEMPLATES:
{catalog}
{gpx_text}{notes_text}

AUFGABE PRO SEITE:
1. Waehle das passende Template AUS DER KATEGORIE des Plans
2. Weise die Bilder den richtigen Slots zu
3. Generiere kurze Bildunterschriften (1 Satz, sachlich, Deutsch)

REGELN:
- Template nicht >2x hintereinander
- Template muss genug Slots haben
- image_index MUSS aus den im Plan zugewiesenen Indizes stammen

ZUSAETZLICHE AUFGABEN:
5. Generiere einen kurzen, stimmungsvollen Seitentitel (2-5 Woerter, Deutsch) — Feld "title" pro Seite
6. Generiere fuer jedes Bild eine aussagekraeftige Bildunterschrift (1 Satz, sachlich, Deutsch) — Feld "caption" im jeweiligen Slot

ANTWORTE NUR mit JSON-Array:
[{{"template_id": "hero_single", "page_type": "single", "title": "Gipfelstuermer", "slots": [{{"slot_id": "main", "image_index": 3, "caption": "Der steile Aufstieg zum Gipfelgrat bei klarer Sicht"}}]}}]"""


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
                            valid_slots.append({k: v for k, v in slot.items() if k != "image_index"})
                    page = PageDescription(
                        template_id=pd.get("template_id", "grid_2x2"),
                        page_type=pd.get("page_type", "single"),
                        slots=valid_slots,
                    )
                    # Titel als title-Slot anhängen (vom Renderer als Überschrift gerendert)
                    if pd.get("title"):
                        page.slots.append({"slot_id": "title", "text": pd["title"]})
                    result.append(page)
                if result:
                    return result
    except Exception as e:
        print(f"⚠️ Pass 2 (Generierung) fehlgeschlagen: {e}")

    # Fallback: nutze Template-Kategorien aus dem Plan (Pass 1)
    CATEGORY_DEFAULTS = {
        "hero": "hero_single",
        "split": "split_equal",
        "grid": "grid_2x2",
        "strip": "strip_3",
        "mixed": "image_text_left",
        "collection": "collection_3",
    }
    all_templates = load_all_templates()
    fallback = []
    for plan_page in pages_plan:
        category = plan_page.get("template_category", "grid")
        template_id = CATEGORY_DEFAULTS.get(category, "grid_2x2")
        tmpl = all_templates.get(template_id)
        if tmpl is None:
            tmpl = all_templates.get("grid_2x2")
            template_id = "grid_2x2"
        indices = plan_page.get("image_indices", [])
        image_slots = [s.id for s in tmpl.slots if s.type == "image"]
        slots = []
        for sid, idx in zip(image_slots, indices):
            slot = {"slot_id": sid, "image_index": idx}
            slots.append(slot)
        fallback.append(PageDescription(
            template_id=template_id,
            page_type=tmpl.page_type,
            slots=slots,
        ))
    return fallback
