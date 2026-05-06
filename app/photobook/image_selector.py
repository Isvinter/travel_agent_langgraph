"""LLM-basierte Bildauswahl fuer das Fotobuch.

Andere Kriterien als die Blog-Bildauswahl: Fokus auf Layout-Eignung,
visuelle Varianz und narrative Verwendbarkeit.
Verarbeitet Bilder in Batches wenn der Context zu gross wuerde.
"""

import json
import math
import re
from typing import Any, Dict, List, Optional
import requests
from app.config import OLLAMA_BASE_URL
from app.state import ImageData
from app.utils.image_utils import encode_image_base64


BATCH_SIZE = 10  # Bilder pro Batch (vermeidet Context-Überlauf)


def _build_batch_prompt(
    batch_size: int,
    select_count: int,
    batch_start: int,
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

Zeige {batch_size} Bilder (chronologisch, Index {batch_start}-{batch_start + batch_size - 1}).
Waehle die {select_count} BESTEN Bilder daraus fuer ein A4-Fotobuch.

KRITERIEN:
1. Starke Bilder bevorzugen — klare Motive, gute Belichtung, scharfe Details
2. Narrative Abdeckung — verschiedene Phasen der Tour abbilden
3. Visuelle Varianz — Perspektiven, Motive, Farben mischen
4. Layout-Eignung — nicht nur Landschaften, auch Details und Portraets

ANTWORTE AUSSCHLIESSLICH mit diesem JSON:
{{"selected_indices": [{batch_start}, {batch_start + 2}, ...]}}"""


def _select_batch(
    batch_images: List[ImageData],
    select_count: int,
    batch_start: int,
    gpx_stats: Optional[Dict[str, Any]],
    notes: Optional[str],
    model: str,
    base_url: str,
) -> List[int]:
    """Fragt das LLM nach den besten Bildern aus einem Batch."""
    encoded = []
    for img in batch_images:
        b64 = encode_image_base64(img.path)
        if b64:
            encoded.append(b64)

    if not encoded:
        return []

    prompt = _build_batch_prompt(len(encoded), select_count, batch_start, gpx_stats, notes)

    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/api/chat",
            json={
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": prompt,
                    "images": encoded,
                }],
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 512},
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
                return [i for i in indices if batch_start <= i < batch_start + len(batch_images)]
    except Exception as e:
        print(f"  ⚠️ Batch-Auswahl fehlgeschlagen: {e}")

    return []


def select_photobook_images(
    images: List[ImageData],
    gpx_stats: Optional[Dict[str, Any]],
    notes: Optional[str],
    model: str = "gemma4:26b-ctx128k",
    photo_count: int = 16,
    base_url: str = OLLAMA_BASE_URL,
) -> List[ImageData]:
    """Waehlt Bilder fuer das Fotobuch via LLM in Batches aus."""
    if not images:
        return []

    target = min(photo_count, len(images))
    if target >= len(images):
        return list(images)

    # Batching: teile Bilder in Gruppen zu je BATCH_SIZE
    num_batches = math.ceil(len(images) / BATCH_SIZE)
    per_batch = math.ceil(target / num_batches)

    print(f"📸 Waehle {target} Bilder aus {len(images)} in {num_batches} Batches...")

    all_indices = []
    for batch_idx in range(num_batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(images))
        batch = images[start:end]
        remaining = target - len(all_indices)
        if remaining <= 0:
            break
        select = min(per_batch, remaining, len(batch))

        print(f"  Batch {batch_idx + 1}/{num_batches}: Bilder {start}-{end - 1}, waehle {select}...")
        indices = _select_batch(batch, select, start, gpx_stats, notes, model, base_url)
        all_indices.extend(indices)
        print(f"    → {len(indices)} ausgewaehlt: {indices}")

    selected = [images[i] for i in all_indices if 0 <= i < len(images)]
    selected = selected[:target]

    # Fallback 1: wenn kein Batch Bilder encodieren konnte, versuche Auswahl ohne Bilder
    all_failed = all(not encode_image_base64(img.path) for img in images[:BATCH_SIZE])
    if all_failed and len(selected) < max(5, target // 2):
        print(f"⚠️ Bild-Encoding fehlgeschlagen, versuche Auswahl ohne Bilder...")
        prompt = f"""Wähle die {target} besten Indizes aus 0-{len(images)-1} für ein Fotobuch.
ANTWORTE NUR: {{"selected_indices": [0, 2, 5, ...]}}"""
        try:
            resp = requests.post(
                f"{base_url.rstrip('/')}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": 512},
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
                    selected = selected[:target]
        except Exception:
            pass

    # Fallback 2: verwende die Bilder in chronologischer Reihenfolge
    if len(selected) < max(5, target // 2):
        print(f"⚠️ Nur {len(selected)} Bilder via LLM ausgewaehlt, verwende chronologische Reihenfolge")
        return list(images)[:target]

    print(f"✅ {len(selected)} Bilder ausgewaehlt")
    return selected
