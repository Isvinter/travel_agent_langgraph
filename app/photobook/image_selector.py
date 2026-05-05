"""LLM-basierte Bildauswahl fuer das Fotobuch.

Andere Kriterien als die Blog-Bildauswahl: Fokus auf Layout-Eignung,
visuelle Varianz und narrative Verwendbarkeit.
"""

import json
import re
from typing import Any, Dict, List, Optional
import requests
from app.config import OLLAMA_BASE_URL
from app.state import ImageData


def _build_selection_prompt(
    image_count: int,
    target_count: int,
    gpx_stats_d: Optional[Dict[str, Any]],
    notes: Optional[str],
) -> str:
    gpx_text = ""
    if gpx_stats_d:
        dist = gpx_stats_d.get("total_distance_m", 0) / 1000
        elev = gpx_stats_d.get("elevation_gain_m", 0)
        gpx_text = f"Tour-Daten: {dist:.1f} km Distanz, {elev:.0f}m Hoehenmeter. "
    notes_text = f"Tour-Notizen: {notes}" if notes else ""

    return f"""Du bist Bildredakteur fuer ein Fotobuch einer Wandertour.

{gpx_text}{notes_text}

VERFUEGBAR: {image_count} Bilder (chronologisch sortiert, Index 0-{image_count - 1}).
GESUCHT: {target_count} Bilder fuer ein A4-Fotobuch.

KRITERIEN:
1. Starke Bilder bevorzugen — klare Motive, gute Belichtung
2. Narrative Abdeckung — Anfang, Mitte und Ende der Tour abbilden
3. Visuelle Varianz — verschiedene Perspektiven und Motive mischen
4. Layout-Eignung — nicht nur Landschaften, auch Details und Portraets

ANTWORTE AUSSCHLIESSLICH mit diesem JSON:
{{"selected_indices": [0, 2, 5, 7, ...]}}"""


def select_photobook_images(
    images: List[ImageData],
    gpx_stats: Optional[Dict[str, Any]],
    notes: Optional[str],
    model: str = "gemma4:26b-ctx128k",
    photo_count: int = 16,
    base_url: str = OLLAMA_BASE_URL,
) -> List[ImageData]:
    """Waehlt Bilder fuer das Fotobuch via LLM aus."""
    if not images:
        return []

    target = min(photo_count, len(images))
    if target >= len(images):
        return list(images)

    prompt = _build_selection_prompt(len(images), target, gpx_stats, notes)

    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 1024},
                "keep_alive": "10m",
            },
            timeout=120,
        )
        if resp.status_code == 200:
            content = resp.json().get("message", {}).get("content", "")
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                indices = data.get("selected_indices", [])
                selected = [images[i] for i in indices if 0 <= i < len(images)]
                if len(selected) >= min(target, 5):
                    return selected[:target]
    except Exception as e:
        print(f"⚠️ Fotobuch-Bildauswahl fehlgeschlagen: {e}")

    print(f"⚠️ Verwende Fallback: erste {target} Bilder")
    return list(images[:target])
