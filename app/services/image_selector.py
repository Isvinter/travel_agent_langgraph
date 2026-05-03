# app/services/image_selector.py
"""Batch-weise Bildauswahl mit multimodalem LLM.

Teilt alle Bilder in Batches auf, sendet je Batch an Ollama, und
reduziert die Auswahl schrittlich auf die gewünschte Endanzahl.
"""

import math
from typing import Any, Dict, List, Optional

from app.config import OLLAMA_BASE_URL


BATCH_SIZE = 15


def select_images_for_blog(
    images: List[Dict[str, Any]],
    target_count: int = 8,
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
) -> List[Dict[str, Any]]:
    """Wählt die besten Bilder für den Blogpost in zwei Schritten:

    1. Alle Bilder auf Batches aufteilen, pro Batch Vorwahl treffen
    2. Kombinierte Vorwahl auf target_count reduzieren

    Returns:
        Liste der ausgewählten Bild-Dictionaries (max target_count).
    """
    if len(images) <= target_count:
        return images

    n_batches = math.ceil(len(images) / BATCH_SIZE)
    picks_per_batch = max(1, math.ceil(target_count / n_batches))

    # Schritt 1: pro Batch auswählen
    all_picks: list[dict[str, Any]] = []
    for batch_idx in range(n_batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(images))
        batch = images[start:end]

        picks_in_batch = min(picks_per_batch, len(batch))
        picks = _select_from_batch(batch, picks_in_batch, model, base_url)
        all_picks.extend(picks)

    # Schritt 2: finale Reduktion auf target_count
    if len(all_picks) <= target_count:
        return all_picks

    return _reduce_to_target(all_picks, target_count, model, base_url)


def _select_from_batch(
    batch: List[Dict[str, Any]],
    target_count: int,
    model: str,
    base_url: str,
) -> List[Dict[str, Any]]:
    encoded = []
    for img in batch:
        try:
            b64 = _encode_image(img["path"])
            if b64:
                encoded.append(b64)
        except Exception:
            continue

    if len(encoded) <= target_count:
        return batch  # alle passen rein

    prompt = _make_batch_prompt(encoded, target_count)
    response = _call_ollama(prompt, encoded, model, base_url)

    if not response:
        # Fallback: gleichmäßig verteilen
        step = max(1, len(encoded) // target_count)
        indices = range(0, len(encoded), step)[:target_count]
        return [batch[i] for i in indices if i < len(batch)]

    indices = _parse_selection(response, max_index=len(encoded) - 1)
    if indices:
        return [batch[i] for i in indices if i < len(batch)]

    # Fallback: erste target_count Bilder
    return batch[:target_count]


def _reduce_to_target(
    candidates: List[Dict[str, Any]],
    target_count: int,
    model: str,
    base_url: str,
) -> List[Dict[str, Any]]:
    encoded = []
    for img in candidates:
        try:
            b64 = _encode_image(img["path"])
            if b64:
                encoded.append(b64)
        except Exception:
            continue

    if len(encoded) <= target_count:
        return candidates[:target_count]

    prompt = _make_final_prompt(encoded, target_count)
    response = _call_ollama(prompt, encoded, model, base_url)

    if not response:
        return [candidates[i] for i in range(target_count)]

    indices = _parse_selection(response, max_index=len(encoded) - 1)
    if indices:
        return [candidates[i] for i in indices if i < len(candidates)]

    return [candidates[i] for i in range(target_count)]


def _encode_image(path: str) -> Optional[str]:
    from PIL import Image
    with Image.open(path) as img:
        if max(img.size) > 600:
            img.thumbnail((600, 600))
        buf = __import__("io").BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=60)
        import base64
        return base64.b64encode(buf.getvalue()).decode("utf-8")


def _make_batch_prompt(images: List[str], target: int) -> str:
    return (
        f"Du erhältst {len(images)} Fotos aus einer Wanderung.\n"
        f"Wähle die {target} besten Bilder für einen Reiseblog.\n"
        "Kriterien: landschaftliche Vielfalt, unterschiedliche Motive "
        "(Landschaft, Detail, Weitwinkel, Portrait) — keine ähnlichen Bilder.\n"
        "Antworte NUR mit den 0-basierten Indexnummern, kommagetrennt, "
        "aufsteigend. Keine Erklärung.\n\n"
        + "\n".join(f"--- Bild {i} ---" for i in range(len(images)))
    )


def _make_final_prompt(images: List[str], target: int) -> str:
    return (
        f"Finale Auswahl: {len(images)} vorgewählte Bilder, "
        f"nur {target} bleiben.\n\n"
        f"Wähle die {target} besten Bilder. Keine ähnlichen Motive. "
        "Antworte NUR mit den 0-basierten Indexnummern, kommagetrennt.\n\n"
        + "\n".join(f"--- Bild {i} ---" for i in range(len(images)))
    )


def _call_ollama(
    prompt: str,
    images: List[str],
    model: str,
    base_url: str,
) -> Optional[str]:
    import requests

    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": prompt,
            "images": images,
        }],
        "stream": False,
        "options": {
            "temperature": 0.0,
            "top_p": 0.1,
            "num_predict": 128,
        },
    }

    try:
        resp = requests.post(f"{base_url}/api/chat", json=payload, timeout=90)
        if resp.status_code == 200:
            return resp.json().get("message", {}).get("content")
    except Exception as e:
        print(f"⚠️ Ollama select failed: {e}")
    return None


def _parse_selection(text: str, max_index: int) -> List[int]:
    import re
    numbers = re.findall(r'\d+', text)
    return sorted({int(n) for n in numbers if int(n) <= max_index})
