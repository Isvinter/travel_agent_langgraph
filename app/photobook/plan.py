"""LLM Pass 1: Preset-Auswahl (pro Seite ein Preset aus 21 Optionen).

Das LLM wählt für jede Seite ein Preset basierend auf Bildanzahl und Text-Bedarf.
Variety-Regeln im Prompt sorgen für Abwechslung.
"""

import json
import re
from typing import Any, Dict, List, Optional
import requests
from app.config import OLLAMA_BASE_URL
from app.state import ImageData, WeatherInfo
from app.utils.image_utils import encode_image_base64
from app.photobook.presets import get_preset_summary, get_any_preset, PhotobookPreset, get_photobook_preset


def _build_plan_prompt(
    image_count: int,
    gpx_stats_d: Optional[Dict[str, Any]],
    notes: Optional[str],
    weather: Optional[WeatherInfo],
    poi_count: int,
    page_range: Optional[str] = None,
    preset: Optional[PhotobookPreset] = None,
) -> str:
    context_parts = [f"BILDER: {image_count} Fotos (chronologisch sortiert, Index 0-{image_count - 1})"]
    if gpx_stats_d:
        dist = gpx_stats_d.get("total_distance_m", 0) / 1000
        elev = gpx_stats_d.get("elevation_gain_m", 0)
        context_parts.append(f"TOUR: {dist:.1f} km, {elev:.0f}m Hoehenmeter")
    if weather and weather.daily:
        context_parts.append(f"WETTER: {weather.summary}")
    if poi_count > 0:
        context_parts.append(f"POIs: {poi_count} Sehenswuerdigkeiten")
    if notes:
        context_parts.append(f"NOTIZEN: {notes}")
    context = "\n".join(context_parts)

    preset_catalog = get_preset_summary()

    page_range_hint = ""
    if page_range:
        page_range_hint = (
            f"\nSEITENZIEL: Erstelle {page_range} Seiten. "
            "Verwende ueberwiegend Presets mit 1 Bild (single_full, single_text_below), "
            "nur gelegentlich 2- oder 3-Bild-Presets fuer Abwechslung. "
            "Vermeide 4-Bild-Presets (quad_grid) so weit wie moeglich — "
            "das Fotobuch soll viele Einzelseiten mit grossen Bildern haben.\n"
        )

    theme_block = ""
    if preset and preset.layout_preferences:
        theme_block = f"\nTHEMA: {preset.name}\n{preset.layout_preferences}\n"

    return f"""Du bist Fotobuch-Art-Director fuer eine Wandertour.

{context}{page_range_hint}
PRESETS (waehle eins pro Seite):
{preset_catalog}

VARIETY-REGELN (UNBEDINGT EINHALTEN):
1. Maximal 2x das gleiche Preset im gesamten Buch (cover_hero NUR auf Seite 0, niemals woanders)
2. Nicht 2x hintereinander das gleiche Preset
3. Maximal 3 Seiten ohne Text hintereinander
4. Nicht 3x hintereinander die gleiche Bildanzahl
5. Dramatischer Bogen: Cover (cover_hero) -> ruhiger Start (1-Bild) -> Aufbau (2-3 Bilder) -> Hoehepunkt (4-Bild) -> Ausklang (1-Bild)
6. Seite 0 MUSS cover_hero sein
{theme_block}
PLANE die Seitenabfolge. Gib JEDEM Bild einen Platz — alle {image_count} Bilder muessen verwendet werden.

ANTWORTE AUSSCHLIESSLICH mit diesem JSON:
{{"pages": [{{"position": 0, "preset_id": "cover_hero", "image_indices": [3], "purpose": "Cover"}}], "dramatic_arc": "kurze Beschreibung"}}"""


def _generate_fallback_plan(images: List[ImageData], image_count: int) -> Dict[str, Any]:
    """Deterministische Fallback-Planung: chronologische Einzelbilder.
    
    Verwendet ueberwiegend single_full-Presets (1 Bild pro Seite), damit alle
    Bilder im Fotobuch erscheinen und die Seitenanzahl der Bildanzahl entspricht.
    Nur wenn viele Bilder uebrig sind, werden 2-Bild-Presets eingestreut.
    """
    indices = list(range(min(image_count, len(images))))
    pages = []
    if indices:
        pages.append({
            "position": 0,
            "preset_id": "cover_hero",
            "image_indices": [indices.pop(0)],
            "purpose": "Cover",
        })
    pos = 1
    while indices:
        remaining = len(indices)
        if remaining >= 2:
            pid = get_any_preset(2)
            pages.append({
                "position": pos,
                "preset_id": pid,
                "image_indices": [indices.pop(0), indices.pop(0)],
                "purpose": "Vergleich",
            })
        else:
            pages.append({
                "position": pos,
                "preset_id": "single_full",
                "image_indices": [indices.pop(0)],
                "purpose": "Einzelbild",
            })
        pos += 1
    return {"pages": pages, "dramatic_arc": "Fallback: chronologische Einzelbilder"}


def _all_images_used(plan: Dict[str, Any], image_count: int) -> bool:
    """Prueft, ob alle verfuegbaren Bilder im Plan verwendet werden."""
    used = set()
    for page in plan.get("pages", []):
        for idx in page.get("image_indices", []):
            if 0 <= idx < image_count:
                used.add(idx)
    return len(used) >= image_count


def plan_photobook_layout(
    images: List[ImageData],
    gpx_stats: Optional[Dict[str, Any]],
    notes: Optional[str],
    weather: Optional[WeatherInfo],
    poi_list: List[Dict[str, Any]],
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
    page_range: str = "",
    preset: Optional[PhotobookPreset] = None,
) -> Dict[str, Any]:
    if not images:
        return {"pages": [], "dramatic_arc": ""}

    if preset is None:
        preset = get_photobook_preset("mixed")

    prompt = _build_plan_prompt(
        len(images), gpx_stats, notes, weather, len(poi_list),
        page_range=page_range if page_range else None,
        preset=preset,
    )

    # Bilder als Base64 encodieren
    encoded_images = []
    for img in images:
        b64 = encode_image_base64(img.path)
        if b64:
            encoded_images.append(b64)

    # Bilder als Base64 encodieren
    encoded_images = []
    for img in images:
        b64 = encode_image_base64(img.path)
        if b64:
            encoded_images.append(b64)

    plan = None
    try:
        payload = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": prompt,
                "images": encoded_images,
            }],
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 4096},
            "keep_alive": "10m",
        }
        resp = requests.post(
            f"{base_url.rstrip('/')}/api/chat",
            json=payload,
            timeout=300,
        )
        if resp.status_code == 200:
            content = resp.json().get("message", {}).get("content", "")
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                plan = json.loads(json_match.group())
                if "pages" in plan and len(plan["pages"]) > 0:
                    # Pruefe, ob alle Bilder verwendet wurden
                    if _all_images_used(plan, len(images)):
                        return plan
                    else:
                        print("⚠️ LLM-Plan verwendet nicht alle Bilder, verwende Fallback")
    except Exception as e:
        print(f"⚠️ Pass 1 (Planung) fehlgeschlagen: {e}")
    return _generate_fallback_plan(images, len(images))
