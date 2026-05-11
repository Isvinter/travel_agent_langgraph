"""LLM Pass 2: Slot-Zuweisung + Text innerhalb von Preset-Constraints."""

import json
import logging
import re
from typing import List, Optional
from app.config import OLLAMA_BASE_URL, PHOTOBOOK_BATCH_SIZE
from app.services.ollama_client import call_ollama, strip_thinking_tokens
from app.state import ImageData, PageDescription, PhotobookPlan, PagePlan, PageSlot
from app.photobook.preset_loader import load_all_presets
from app.photobook.presets import get_any_preset, get_photobook_preset, get_preset_text_ranges
from app.photobook.presets import PhotobookPreset
from app.utils.image_utils import encode_image_base64

logger = logging.getLogger(__name__)


# ── Batch-Hilfsfunktionen ──


def _split_into_batches(pages: List[PagePlan], batch_size: int) -> List[List[PagePlan]]:
    """Teilt Seiten chronologisch in Batches."""
    return [pages[i:i + batch_size] for i in range(0, len(pages), batch_size)]


def _images_for_batch(batch_pages: List[PagePlan], all_images: List[ImageData]) -> List[ImageData]:
    """Ermittelt die Menge der im Batch referenzierten Bilder (dedupliziert, sortiert)."""
    used_indices: set[int] = set()
    for page in batch_pages:
        used_indices.update(page.image_indices)
    return [all_images[i] for i in sorted(used_indices) if 0 <= i < len(all_images)]


def calculate_num_predict(
    batch_pages: List[PagePlan],
    safety_factor: float = 1.5,
    min_tokens: int = 8192,
) -> int:
    """Berechnet num_predict aus der Summe der char_limits aller Text-Slots im Batch."""
    max_chars = 0
    for page in batch_pages:
        try:
            text_ranges = get_preset_text_ranges(page.preset_id)
        except (FileNotFoundError, Exception):
            continue
        for slot_id, (ch_min, ch_max) in text_ranges.items():
            max_chars += ch_max
    text_tokens = max_chars / 2.5
    json_overhead = 2000
    return max(min_tokens, int((text_tokens + json_overhead) * safety_factor))


# ── Batch Prompt Template ──

BATCH_PROMPT_TEMPLATE = """Du befuellst die Slots der gewaehlten Presets mit Bildern und Text.

TOUR: {tour_summary}
TOURDATEN: {gpx_text}

SEITENPLAN (nur dieser Batch):
{plan_text}

VERWENDETE PRESETS (nur diese sind relevant):
{catalog}

AUFGABE PRO SEITE:{style_block}
1. Weise jedem Image-Slot ein Bild zu (image_index aus dem Plan).
2. TEXT-PFLICHT: Jeder in der Preset-Liste oben als "text" markierte Slot (title, caption, intro, ...) MUSS einen nicht-leeren text-Wert bekommen. Lass KEINEN Text-Slot leer. Ein Preset OHNE Text-Slots (Text=nein) braucht natuerlich keinen Text.
3. Textdimensionen: title max. 60 Zeichen. caption und intro: char_max siehe Preset-Liste oben ([min-maxZ]) — ueberschreite NIEMALS char_max. Die char_min-Angabe ist eine Empfehlung fuer ausfuehrlichen Text, keine harte Pflicht.
4. Generiere AUSFUEHRLICHE, lebendige Texte — beschreibe Landschaft, Stimmung, Farben, Details, Wetter. Je mehr Details desto besser.
{title_instruction}{multi_image_instruction}

VOR DER AUSGABE PRUEFEN:
- Hat JEDE Seite einen title-Slot mit nicht-leerem Text?
- Hat JEDE Seite fuer ALLE im Preset vorhandenen Text-Slots (caption, intro, ...) einen nicht-leeren text-Eintrag?
- Sind alle char_min/char_max eingehalten?

BEISPIELE:
- cover_hero: [{{"preset_id": "cover_hero", "slots": [{{"slot_id": "title", "text": "Aufbruch im Morgengrauen"}}, {{"slot_id": "main", "image_index": 0}}]}}]
- single_text_below: [{{"preset_id": "single_text_below", "slots": [{{"slot_id": "title", "text": "Alpenwiese"}}, {{"slot_id": "main", "image_index": 1}}, {{"slot_id": "caption", "text": "Ein atemberaubender Weitblick ueber das Tal..."}}]}}]"""


def _build_batch_prompt(
    batch_pages: List[PagePlan],
    tour_summary: Optional[str],
    gpx_distance: Optional[str],
    gpx_elevation: Optional[str],
    preset: Optional[PhotobookPreset] = None,
) -> str:
    if preset is None:
        preset = get_photobook_preset("mixed")

    all_presets = load_all_presets()
    used_preset_ids = set()
    for pp in batch_pages:
        if pp.preset_id:
            used_preset_ids.add(pp.preset_id)

    preset_summary = []
    for pid in sorted(used_preset_ids):
        p = all_presets.get(pid)
        if p:
            text_ranges = get_preset_text_ranges(pid)
            slot_info_parts = []
            for s in p.slots:
                slot_label = f"{s.id}({s.type},{s.text_role or s.priority or '-'})"
                if s.id in text_ranges:
                    ch_min, ch_max = text_ranges[s.id]
                    slot_label += f"[{ch_min}-{ch_max}Z]"
                slot_info_parts.append(slot_label)
            slot_info = ", ".join(slot_info_parts)
            preset_summary.append(f"  {pid} [{p.image_count} Bilder, Text={'ja' if p.has_text else 'nein'}]: {slot_info}")
    catalog = "\n".join(preset_summary)

    serializable_pages = [pp.model_dump() for pp in batch_pages]
    plan_text = json.dumps(serializable_pages, indent=2, ensure_ascii=False)

    gpx_text = ""
    if gpx_distance and gpx_elevation:
        gpx_text = f"{gpx_distance} km, {gpx_elevation}m Hoehenmeter."
    elif gpx_distance:
        gpx_text = f"{gpx_distance} km."
    else:
        gpx_text = "Keine Daten."

    summary = tour_summary if tour_summary else "Keine Zusammenfassung verfuegbar."

    style_block = ""
    if preset.generation_instructions:
        style_block = f"\nSTILVORGABE ({preset.name}): {preset.generation_instructions}\n"

    title_instruction = "5. JEDE Seite MUSS einen title-Slot haben: " + '{"slot_id": "title", "text": "Einzeiliger Seitentitel"}' if preset.text_enabled else ""
    multi_image_instruction = "\n6. Bei Presets mit MEHREREN Bildern (quad_grid, double_stacked, triple_stacked): beschreibe den Gesamteindruck der Bildgruppe, nicht nur ein einzelnes Bild." if preset.text_enabled else ""

    return BATCH_PROMPT_TEMPLATE.format(
        tour_summary=summary,
        gpx_text=gpx_text,
        plan_text=plan_text,
        catalog=catalog,
        style_block=style_block,
        title_instruction=title_instruction,
        multi_image_instruction=multi_image_instruction,
    )


def _validate_batch_result(
    result_json: list,
    batch_pages: List[PagePlan],
) -> tuple:
    """Validiert ein Batch-Ergebnis. Returns (ok: bool, error_message: Optional[str])."""
    if not isinstance(result_json, list):
        return False, "Kein JSON-Array"

    if len(result_json) != len(batch_pages):
        return False, f"Seitenanzahl ({len(result_json)}) != erwartet ({len(batch_pages)})"

    all_presets = load_all_presets()
    for i, page_data in enumerate(result_json):
        if not isinstance(page_data, dict):
            return False, f"Seite {i}: Kein Dictionary"
        preset_id = page_data.get("preset_id", "")
        preset = all_presets.get(preset_id)
        if not preset:
            return False, f"Seite {i}: Unbekanntes Preset '{preset_id}'"
        slots = page_data.get("slots", [])
        slot_map = {s.get("slot_id", ""): s for s in slots}

        title_slot = slot_map.get("title")
        if not title_slot or not title_slot.get("text", "").strip():
            return False, f"Seite {i}: Fehlender oder leerer title-Slot"

        for ps in preset.slots:
            if ps.type == "text":
                slot = slot_map.get(ps.id)
                if not slot:
                    return False, f"Seite {i}: Fehlender Text-Slot '{ps.id}'"
                if not slot.get("text", "").strip():
                    return False, f"Seite {i}: Leerer Text-Slot '{ps.id}'"

    return True, None


def _generate_fallback_for_batch(
    batch_pages: List[PagePlan],
    batch_images: List[ImageData],
) -> List[PageDescription]:
    """Generiert Fallback-Seiten fuer einen Batch."""
    all_presets = load_all_presets()
    fallback = []
    for plan_page in batch_pages:
        preset_id = plan_page.preset_id or "quad_grid"
        preset = all_presets.get(preset_id)
        if preset is None:
            count = len(plan_page.image_indices)
            preset_id = get_any_preset(count)
            preset = all_presets.get(preset_id, all_presets["quad_grid"])

        indices = plan_page.image_indices
        image_slots = [s.id for s in preset.slots if s.type == "image"]
        slots = []
        for sid, idx in zip(image_slots, indices):
            if 0 <= idx < len(batch_images):
                slots.append({"slot_id": sid, "image_index": idx})

        purpose = plan_page.purpose
        position = plan_page.position
        if purpose and purpose.lower() not in ("cover", "einzelbild", "sammlung", "sequenz", "vergleich"):
            title = purpose[:60]
        elif position == 0:
            title = "Fotobuch"
        else:
            title = f"Seite {position + 1}"
        slots.append({"slot_id": "title", "text": title})

        for s in preset.slots:
            if s.type == "text" and s.text_role != "title":
                img_indices_str = ", ".join(str(i) for i in indices[:2])
                slot_text = f"Foto {img_indices_str} — Eindrücke der Tour"
                if s.char_limit and len(slot_text) > s.char_limit:
                    slot_text = slot_text[:s.char_limit]
                slots.append({"slot_id": s.id, "text": slot_text})

        fallback.append(PageDescription(
            template_id=preset_id,
            page_type="single",
            slots=[PageSlot(**s) for s in slots],
        ))
    return fallback


# ── Merge-Funktion ──


def _merge_batch_results(all_results: List[list]) -> List[PageDescription]:
    """Deterministisches Mergen aller Batch-Ergebnisse zu PageDescriptions."""
    merged = []
    for batch_result in all_results:
        for pd in batch_result:
            valid_slots = []
            for slot in pd.get("slots", []):
                idx = slot.get("image_index", -1)
                if idx is not None and idx >= 0:
                    valid_slots.append(slot)
                else:
                    cleansed = {k: v for k, v in slot.items() if k != "image_index"}
                    if cleansed.get("text") or cleansed.get("slot_id"):
                        valid_slots.append(cleansed)
            deduped = []
            seen = set()
            for s in reversed(valid_slots):
                sid = s.get("slot_id", "")
                if sid not in seen:
                    seen.add(sid)
                    deduped.append(s)
            deduped.reverse()
            page_slots = [PageSlot(**s) for s in deduped]
            page = PageDescription(
                template_id=pd.get("preset_id", "quad_grid"),
                page_type="single",
                slots=page_slots,
            )
            merged.append(page)
    return merged


def generate_photobook_pages(
    plan: PhotobookPlan,
    images: List[ImageData],
    tour_summary: Optional[str] = None,
    gpx_distance: Optional[str] = None,
    gpx_elevation: Optional[str] = None,
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
    preset: Optional[PhotobookPreset] = None,
    batch_size: int = PHOTOBOOK_BATCH_SIZE,
) -> List[PageDescription]:
    if preset is None:
        preset = get_photobook_preset("mixed")
    pages_plan = plan.pages
    if not pages_plan:
        return []

    batches = _split_into_batches(pages_plan, batch_size)
    logger.info("Generiere %s Seiten in %s Batches (batch_size=%s)...", len(pages_plan), len(batches), batch_size)

    all_results = []
    for batch_idx, batch_pages in enumerate(batches):
        logger.info("Batch %s/%s: %s Seiten", batch_idx + 1, len(batches), len(batch_pages))
        batch_images = _images_for_batch(batch_pages, images)

        prompt = _build_batch_prompt(
            batch_pages,
            tour_summary,
            gpx_distance,
            gpx_elevation,
            preset=preset,
        )

        encoded_images = []
        for img in batch_images:
            b64 = encode_image_base64(img.path)
            if b64:
                encoded_images.append(b64)

        num_pred = calculate_num_predict(batch_pages)

        batch_result = None
        for attempt in range(2):
            try:
                content = call_ollama(
                    prompt,
                    model=model,
                    base_url=base_url,
                    images=encoded_images,
                    temperature=0.3,
                    num_predict=num_pred,
                    timeout=120,
                    disable_thinking=True,
                )
                if content:
                    content = strip_thinking_tokens(content)
                    array_match = re.search(r'\[.*\]', content, re.DOTALL)
                    if array_match:
                        try:
                            pages_data = json.loads(array_match.group())
                            ok, err_msg = _validate_batch_result(pages_data, batch_pages)
                            if ok:
                                batch_result = pages_data
                                break
                            else:
                                logger.warning("Batch %s Validierung fehlgeschlagen (Versuch %s): %s", batch_idx + 1, attempt + 1, err_msg)
                        except json.JSONDecodeError as je:
                            logger.warning("Batch %s JSON-Parse-Fehler (Versuch %s): %s", batch_idx + 1, attempt + 1, je)
                    else:
                        logger.warning("Batch %s: Kein JSON-Array in LLM-Antwort (Versuch %s)", batch_idx + 1, attempt + 1)
                else:
                    logger.warning("Batch %s: Leere LLM-Antwort (Versuch %s)", batch_idx + 1, attempt + 1)
            except Exception as e:
                logger.warning("Batch %s LLM-Call fehlgeschlagen (Versuch %s): %s", batch_idx + 1, attempt + 1, e)

        if batch_result:
            all_results.append(batch_result)
        else:
            logger.warning("Batch %s: Verwende Fallback nach %s Versuchen", batch_idx + 1, 2)
            fallback = _generate_fallback_for_batch(batch_pages, batch_images)
            all_results.append([{
                "preset_id": fb.template_id,
                "slots": [s.model_dump() for s in fb.slots],
            } for fb in fallback])

    return _merge_batch_results(all_results)
