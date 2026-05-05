"""LLM Pass 1: Layout-Planung (Dramaturgie + Seiten-Sequenz).

Das LLM plant die Seitenabfolge auf Kategorie-Ebene.
"""

import json
import re
from typing import Any, Dict, List, Optional
import requests
from app.config import OLLAMA_BASE_URL
from app.state import ImageData, WeatherInfo
from app.utils.image_utils import encode_image_base64


def _build_plan_prompt(
    image_count: int,
    gpx_stats_d: Optional[Dict[str, Any]],
    notes: Optional[str],
    weather: Optional[WeatherInfo],
    poi_count: int,
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

    return f"""Du bist Fotobuch-Art-Director fuer eine Wandertour.

{context}

TEMPLATE-KATEGORIEN:
- hero: 1 grosses Bild (Cover, Kapitelanfang, Schluesselmomente)
- split: 2 Bilder nebeneinander (Vergleiche, Vorher/Nachher)
- grid: 3-4 Bilder im Raster (Sammlungen, Details)
- strip: 3 Bilder horizontal (Sequenzen, Zeitablaeufe)
- mixed: Bild + Textblock (Kontext, Einleitungen)
- collection: 1 grosses + 2 kleine (thematische Gruppen)

GLOBALE LAYOUT-REGELN:
1. Cover (Pos. 0) und letzte Seite sind hero-Templates
2. Maximal 2x das gleiche Template hintereinander
3. Alle 4-6 Seiten ein hero-Anker
4. Wechsel zwischen dichten Seiten (grid) und ruhigen (single)
5. Wichtigere Bilder bekommen groessere Slots

PLANE die Seitenabfolge. Gib jedem Bild einen Platz.
Struktur: Cover -> Aufbau -> Highlights -> Variation -> Abschluss

ANTWORTE AUSSCHLIESSLICH mit diesem JSON:
{{"pages": [{{"position": 0, "page_type": "cover", "template_category": "hero", "image_indices": [3], "purpose": "Beschreibung"}}], "dramatic_arc": "kurze Beschreibung"}}"""


def _generate_fallback_plan(images: List[ImageData], image_count: int) -> Dict[str, Any]:
    indices = list(range(min(image_count, len(images))))
    pages = []
    if indices:
        pages.append({"position": 0, "page_type": "cover", "template_category": "hero", "image_indices": [indices.pop(0)], "purpose": "Cover"})
    pos = 1
    while indices:
        if len(indices) >= 4:
            pages.append({"position": pos, "page_type": "single", "template_category": "grid", "image_indices": [indices.pop(0) for _ in range(min(4, len(indices)))], "purpose": "Sammlung"})
        elif len(indices) >= 2:
            pages.append({"position": pos, "page_type": "spread", "template_category": "split", "image_indices": [indices.pop(0), indices.pop(0)], "purpose": "Vergleich"})
        else:
            pages.append({"position": pos, "page_type": "single", "template_category": "hero", "image_indices": [indices.pop(0)], "purpose": "Einzelbild"})
        pos += 1
    return {"pages": pages, "dramatic_arc": "Fallback: lineare Sequenz"}


def plan_photobook_layout(
    images: List[ImageData],
    gpx_stats: Optional[Dict[str, Any]],
    notes: Optional[str],
    weather: Optional[WeatherInfo],
    poi_list: List[Dict[str, Any]],
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
) -> Dict[str, Any]:
    if not images:
        return {"pages": [], "dramatic_arc": ""}
    prompt = _build_plan_prompt(len(images), gpx_stats, notes, weather, len(poi_list))
    
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
                    return plan
    except Exception as e:
        print(f"⚠️ Pass 1 (Planung) fehlgeschlagen: {e}")
    return _generate_fallback_plan(images, len(images))
