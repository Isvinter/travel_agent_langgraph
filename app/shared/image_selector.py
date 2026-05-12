"""Generischer Batch-basierter Bildselektor (shared zwischen Photobuch und Kalender)."""
import logging
import math
from typing import List, Optional

from app.state import ImageData
from app.services.ollama_client import call_ollama, strip_thinking_tokens
from app.utils.image_utils import encode_image_base64
from app.services.image_selector import _parse_selection

logger = logging.getLogger(__name__)

BATCH_SIZE = 15


def _build_batch_prompt(
    batch_size: int,
    select_count: int,
    criteria: str,
    custom_instructions: Optional[str] = None,
) -> str:
    extra = f"\nZusätzliche Anweisungen: {custom_instructions}" if custom_instructions else ""
    return (
        f"Du erhältst {batch_size} Fotos.\n"
        f"Wähle die {select_count} besten Bilder.\n"
        f"Kriterien: {criteria}{extra}\n"
        f"Antworte NUR mit den 0-basierten Indexnummern, kommagetrennt, aufsteigend. "
        f"Keine Erklärung.\n\n"
        + "\n".join(f"--- Bild {i} ---" for i in range(batch_size))
    )


def _select_batch(
    batch_images: List[ImageData],
    select_count: int,
    criteria: str,
    model: str,
    base_url: str,
    custom_instructions: Optional[str] = None,
) -> tuple[List[int], bool]:
    encoded = []
    index_map = {}
    for i, img in enumerate(batch_images):
        b64 = encode_image_base64(img.path)
        if b64:
            index_map[len(encoded)] = i
            encoded.append(b64)

    if len(encoded) <= select_count:
        return [index_map[i] for i in range(len(encoded))], True

    prompt = _build_batch_prompt(len(encoded), select_count, criteria, custom_instructions)

    response = call_ollama(
        prompt,
        model=model,
        base_url=base_url,
        images=encoded,
        temperature=0.0,
        top_p=0.1,
        num_predict=256,  # nur Index-Nummern, kein langer Text
        timeout=180,
        disable_thinking=True,
    )

    if response:
        content = strip_thinking_tokens(response)
        indices = _parse_selection(content, max_index=len(encoded) - 1)
        if indices:
            return [index_map[i] for i in indices[:select_count] if i in index_map], True

    step = max(1, len(encoded) // select_count)
    return [index_map[i] for i in range(0, len(encoded), step)][:select_count], False


def select_images(
    images: List[ImageData],
    criteria: str = "starke Motive, gute Belichtung, Vielfalt",
    target_count: int = 30,
    model: str = "gemma4:26b-ctx128k",
    base_url: str = "http://localhost:11434",
    custom_instructions: Optional[str] = None,
) -> List[ImageData]:
    """Zweistufige Batch-basierte Bildauswahl.

    Args:
        images: Alle verfügbaren Bilder.
        criteria: Selektionskriterien als Prompt-Text.
        target_count: Zielanzahl ausgewählter Bilder.
        model: Ollama-Modellname.
        base_url: Ollama-Server-URL.
        custom_instructions: Optionale Zusatzanweisungen.

    Returns:
        Liste der ausgewählten ImageData-Objekte (höchstens target_count).
    """
    if not images:
        return []

    target = min(target_count, len(images))
    if target >= len(images):
        return list(images)

    num_batches = math.ceil(len(images) / BATCH_SIZE)
    per_batch = math.ceil(target / num_batches)

    logger.info("Wähle %s Bilder aus %s in %s Batches...", target, len(images), num_batches)

    all_indices = []
    any_llm_success = False
    for batch_idx in range(num_batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(images))
        batch = images[start:end]
        select = min(per_batch, target - len(all_indices), len(batch))
        if select <= 0:
            break

        batch_indices, llm_success = _select_batch(
            batch, select, criteria, model, base_url,
            custom_instructions=custom_instructions,
        )
        if llm_success:
            any_llm_success = True
        global_indices = [start + i for i in batch_indices if i < len(batch)]
        all_indices.extend(global_indices)

    if not any_llm_success:
        logger.warning("Keine LLM-Antwort erhalten, verwende chronologische Reihenfolge")
        return list(images)[:target]

    selected = [images[i] for i in all_indices if 0 <= i < len(images)]
    selected = selected[:target * 2]

    if len(selected) <= target:
        if len(selected) < max(5, target // 2):
            logger.warning("Nur %s via LLM, verwende chronologische Reihenfolge", len(selected))
            return list(images)[:target]
        return selected[:target]

    final_indices, _ = _select_batch(
        selected, target, criteria, model, base_url,
        custom_instructions=custom_instructions,
    )
    final = [selected[i] for i in final_indices if i < len(selected)]
    if len(final) < max(5, target // 2):
        final = selected[:target]

    logger.info("%s Bilder ausgewählt", len(final))
    return final[:target]
