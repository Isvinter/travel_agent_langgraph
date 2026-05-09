"""LLM-basierte Bildauswahl fuer das Fotobuch.

Andere Kriterien als die Blog-Bildauswahl: Fokus auf Layout-Eignung,
visuelle Varianz und narrative Verwendbarkeit.
Verarbeitet Bilder in Batches (gleicher Ansatz wie Blog-Selector).
"""

import math
from typing import Any, Dict, List, Optional
from app.config import OLLAMA_BASE_URL
from app.photobook.presets import PhotobookPreset, get_photobook_preset
from app.services.ollama_client import call_ollama, strip_thinking_tokens
from app.state import ImageData
from app.utils.image_utils import encode_image_base64
from app.services.image_selector import _parse_selection

BATCH_SIZE = 15  # Gleiche Batch-Grösse wie Blog-Selector


def _build_batch_prompt(batch_size: int, select_count: int, preset: PhotobookPreset) -> str:
    criteria = preset.selection_criteria if preset.selection_criteria else (
        "starke Motive, gute Belichtung, landschaftliche Vielfalt, "
        "verschiedene Perspektiven, Details und Porträts mischen."
    )
    return (
        f"Du erhältst {batch_size} Fotos aus einer Wanderung.\n"
        f"Wähle die {select_count} besten Bilder für ein A4-Fotobuch "
        f"({preset.name}).\n"
        f"Kriterien: {criteria}\n"
        "Antworte NUR mit den 0-basierten Indexnummern, kommagetrennt, aufsteigend. "
        "Keine Erklärung.\n\n"
        + "\n".join(f"--- Bild {i} ---" for i in range(batch_size))
    )


def _select_batch(
    batch_images: List[ImageData],
    select_count: int,
    model: str,
    base_url: str,
    preset: PhotobookPreset,
) -> List[int]:
    """Fragt das LLM nach den besten Bildern aus einem Batch.
    Gleicher Ansatz wie Blog-Selector: permissives Parsing, Fallback auf evenly-spaced.
    Verwendet Index-Mapping um Bild-Drops durch fehlgeschlagene Encodierung zu kompensieren.
    """
    # Index-Mapping: encoded_index -> original batch_index
    encoded = []
    index_map: Dict[int, int] = {}
    for i, img in enumerate(batch_images):
        b64 = encode_image_base64(img.path)
        if b64:
            index_map[len(encoded)] = i
            encoded.append(b64)

    if len(encoded) <= select_count:
        return [index_map[i] for i in range(len(encoded))]

    prompt = _build_batch_prompt(len(encoded), select_count, preset)

    response = call_ollama(
        prompt,
        model=model,
        base_url=base_url,
        images=encoded,
        temperature=0.0,
        top_p=0.1,
        num_predict=128,
        timeout=120,
    )

    if response:
        content = strip_thinking_tokens(response)
        indices = _parse_selection(content, max_index=len(encoded) - 1)
        if indices:
            return [index_map[i] for i in indices[:select_count] if i in index_map]

    # Fallback: evenly-spaced
    step = max(1, len(encoded) // select_count)
    return [index_map[i] for i in range(0, len(encoded), step)][:select_count]


def select_photobook_images(
    images: List[ImageData],
    gpx_stats: Optional[Dict[str, Any]],
    notes: Optional[str],
    model: str = "gemma4:26b-ctx128k",
    photo_count: int = 16,
    base_url: str = OLLAMA_BASE_URL,
    preset: Optional[PhotobookPreset] = None,
) -> List[ImageData]:
    """Waehlt Bilder fuer das Fotobuch via LLM in Batches aus.
    Zweistufig: 1) Pro-Batch-Vorauswahl, 2) Finale Reduktion.
    """
    if not images:
        return []

    if preset is None:
        preset = get_photobook_preset("mixed")

    target = min(photo_count, len(images))
    if target >= len(images):
        return list(images)

    num_batches = math.ceil(len(images) / BATCH_SIZE)
    per_batch = math.ceil(target / num_batches)

    print(f"📸 Wähle {target} Bilder aus {len(images)} in {num_batches} Batches...")

    # Step 1: Per-Batch-Auswahl
    all_indices = []
    for batch_idx in range(num_batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(images))
        batch = images[start:end]
        select = min(per_batch, target - len(all_indices), len(batch))
        if select <= 0:
            break

        batch_indices = _select_batch(batch, select, model, base_url, preset)
        global_indices = [start + i for i in batch_indices if i < len(batch)]
        all_indices.extend(global_indices)

    selected = [images[i] for i in all_indices if 0 <= i < len(images)]
    selected = selected[:target * 2]  # Allow oversampling for final reduction

    if len(selected) <= target:
        if len(selected) < max(5, target // 2):
            print(f"⚠️ Nur {len(selected)} via LLM, verwende chronologische Reihenfolge")
            return list(images)[:target]
        print(f"✅ {len(selected)} Bilder ausgewählt")
        return selected[:target]

    # Step 2: Finale Reduktion auf target
    final_indices = _select_batch(selected, target, model, base_url, preset)
    final = [selected[i] for i in final_indices if i < len(selected)]
    if len(final) < max(5, target // 2):
        final = selected[:target]

    print(f"✅ {len(final)} Bilder ausgewählt")
    return final[:target]
