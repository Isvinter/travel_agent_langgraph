"""LLM Pass 2: Slot-Zuweisung + Text innerhalb von Preset-Constraints."""

import json
import logging
import re
from typing import Any, Dict, List, Optional
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
        text_ranges = get_preset_text_ranges(page.preset_id)
        for slot_id, (ch_min, ch_max) in text_ranges.items():
            max_chars += ch_max
    text_tokens = max_chars / 2.5
    json_overhead = 2000
    return max(min_tokens, int((text_tokens + json_overhead) * safety_factor))


# ── Prompt Template ──

GENERATE_PROMPT_TEMPLATE = """Du befuellst die Slots der gewaehlten Presets mit Bildern und Text.

SEITENPLAN (preset_id pro Seite):
{plan_text}

VERWENDETE PRESETS (nur diese sind relevant):
{catalog}
{gpx_text}{notes_text}

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
- single_text_below: [{{"preset_id": "single_text_below", "slots": [{{"slot_id": "title", "text": "Alpenwiese"}}, {{"slot_id": "main", "image_index": 1}}, {{"slot_id": "caption", "text": "Ein atemberaubender Weitblick ueber das Tal. Die Morgensonne taucht die gegenüberliegenden Berggipfel in warmes, goldenes Licht. In der Ferne sind vereinzelte Wanderer auf dem schmalen Gratweg zu erkennen, während unter uns die Nebelschwaden langsam aus dem Tal aufsteigen."}}]}}]
- image_text_split: [{{"preset_id": "image_text_split", "slots": [{{"slot_id": "title", "text": "Historische Altstadt"}}, {{"slot_id": "main", "image_index": 2}}, {{"slot_id": "intro", "text": "Die verwinkelten Gassen fuehren vorbei an jahrhundertealten Fachwerkhaeusern. Kleine Laeden und Cafes säumen den Weg, waehrend die Spaetnachmittagssonne warmes Licht auf die Kopfsteinpflaster wirft. Der Duft von frisch gebackenem Brot liegt in der Luft."}}]}}]"""


def _build_generate_prompt(pages_plan, gpx_stats_d, notes, preset=None):
    if preset is None:
        preset = get_photobook_preset("mixed")

    # pages_plan kann List[PagePlan] oder List[Dict] sein
    def _get_pid(pp):
        if hasattr(pp, "preset_id"):
            return pp.preset_id
        return pp.get("preset_id", "")

    # Nur die tatsächlich im Plan verwendeten Presets laden
    all_presets = load_all_presets()
    used_preset_ids = set()
    for pp in pages_plan:
        pid = _get_pid(pp)
        if pid:
            used_preset_ids.add(pid)

    # Nur relevante Presets anzeigen (mit Char-Ranges fuer Text-Slots)
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

    # Char-Ranges sind bereits im catalog enthalten; keine separaten Constraints noetig.

    # Konvertiere PagePlan-Objekte zu dicts für JSON-Serialisierung
    serializable_pages = []
    for pp in pages_plan:
        if hasattr(pp, "model_dump"):
            serializable_pages.append(pp.model_dump())
        else:
            serializable_pages.append(pp)
    plan_text = json.dumps(serializable_pages, indent=2, ensure_ascii=False)
    gpx_text = ""
    if gpx_stats_d:
        dist = gpx_stats_d.get("total_distance_m", 0) / 1000
        elev = gpx_stats_d.get("elevation_gain_m", 0)
        gpx_text = f"\nTOUR: {dist:.1f} km, {elev:.0f}m Hoehenmeter."
    notes_text = f"\nTOUR-NOTIZEN: {notes}" if notes else ""

    # Text-Pflicht ist jetzt direkt im Prompt-Template verankert (Punkt 2).

    style_block = ""
    if preset.generation_instructions:
        style_block = f"\nSTILVORGABE ({preset.name}): {preset.generation_instructions}\n"

    title_instruction = "5. JEDE Seite MUSS einen title-Slot haben: " + '{"slot_id": "title", "text": "Einzeiliger Seitentitel"}' if preset.text_enabled else ""
    multi_image_instruction = "\n6. Bei Presets mit MEHREREN Bildern (quad_grid, double_stacked, triple_stacked): beschreibe den Gesamteindruck der Bildgruppe, nicht nur ein einzelnes Bild." if preset.text_enabled else ""

    return GENERATE_PROMPT_TEMPLATE.format(
        plan_text=plan_text,
        catalog=catalog,
        gpx_text=gpx_text,
        notes_text=notes_text,
        style_block=style_block,
        title_instruction=title_instruction,
        multi_image_instruction=multi_image_instruction,
    )


def generate_photobook_pages(
    plan: PhotobookPlan,
    images: List[ImageData],
    gpx_stats: Optional[Dict[str, Any]],
    notes: Optional[str],
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
    preset: Optional[PhotobookPreset] = None,
) -> List[PageDescription]:
    if preset is None:
        preset = get_photobook_preset("mixed")
    pages_plan = plan.pages
    if not pages_plan:
        return []
    prompt = _build_generate_prompt(pages_plan, gpx_stats, notes, preset=preset)

    # Bilder als Base64 encodieren
    encoded_images = []
    for img in images:
        b64 = encode_image_base64(img.path)
        if b64:
            encoded_images.append(b64)

    try:
        content = call_ollama(
            prompt,
            model=model,
            base_url=base_url,
            images=encoded_images,
            temperature=0.3,
            num_predict=32768,
            timeout=300,
        )
        if content:
            content = strip_thinking_tokens(content)
            # Debug: zeige LLM-Antwort (Anfang)
            logger.info("LLM Antwort: %s Zeichen", len(content))
            logger.info("Anfang: %s...", content[:200])
            array_match = re.search(r'\[.*\]', content, re.DOTALL)
            if not array_match:
                logger.warning("Kein JSON-Array in LLM-Antwort gefunden!")
            else:
                raw_json = array_match.group()
                try:
                    pages_data = json.loads(raw_json)
                except json.JSONDecodeError as je:
                    logger.warning("JSON-Parse-Fehler: %s. Versuche Recovery...", je)
                    # Versuche, das JSON zu reparieren: schneide beim Fehler ab
                    # und versuche, mit dem bis dahin gültigen Teil zu arbeiten
                    error_pos = je.pos
                    # Finde das letzte vollständige Page-Objekt vor dem Fehler
                    truncated = raw_json[:error_pos]
                    # Suche rückwärts nach einem abschließenden }]
                    last_close = truncated.rfind('}]')
                    if last_close > 0:
                        partial = truncated[:last_close + 2] + ']'
                        try:
                            pages_data = json.loads(partial)
                            logger.info("Recovery: %s von %s Zeichen verwendet", len(pages_data), len(raw_json))
                        except json.JSONDecodeError:
                            # Nochmal mit nur einem schließenden }
                            last_obj = truncated.rfind('},')
                            if last_obj > 0:
                                partial = truncated[:last_obj + 1] + ']'
                                try:
                                    pages_data = json.loads(partial)
                                    logger.info("Recovery (2): %s von %s Zeichen verwendet", len(pages_data), len(raw_json))
                                except json.JSONDecodeError:
                                    logger.warning("Recovery fehlgeschlagen, verwende Fallback")
                                    pages_data = None
                    else:
                        logger.warning("Recovery fehlgeschlagen, verwende Fallback")
                        pages_data = None
                
                if pages_data:
                    # Debug: zeige wie viele Text-Slots das LLM gefuellt hat
                    text_slots = sum(1 for pd in pages_data for s in pd.get("slots", []) if "text" in s)
                    total_pages = len(pages_data)
                    logger.info("LLM hat %s Text-Slots gefüllt (von %s Seiten)", text_slots, total_pages)
                    text_samples = [
                        (pd.get("preset_id","?"), s.get("slot_id","?"), s.get("text","")[:40])
                        for pd in pages_data
                        for s in pd.get("slots", [])
                        if "text" in s and s.get("text", "").strip()
                    ]
                    if text_samples:
                        for pid, sid, t in text_samples[:5]:
                            logger.info("  %s/%s: \"%s...\"", pid, sid, t)
                    elif total_pages > 0:
                        logger.warning("LLM hat KEINE Text-Inhalte generiert!")
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
                        # Dedupliziere Slots: behalte letzten Eintrag pro slot_id
                        deduped = []
                        seen = set()
                        for s in reversed(valid_slots):
                            sid = s.get("slot_id", "")
                            if sid not in seen:
                                seen.add(sid)
                                deduped.append(s)
                        deduped.reverse()
                        # Konvertiere Dict-Slots zu PageSlot-Objekten
                        page_slots = [PageSlot(**s) for s in deduped]
                        page = PageDescription(
                            template_id=pd.get("preset_id", "quad_grid"),
                            page_type="single",
                            slots=page_slots,
                        )
                        result.append(page)
                    if result:
                        return result
    except Exception as e:
        logger.warning("Pass 2 (Generierung) fehlgeschlagen: %s", e)

    # Fallback: verwende das im Plan gewählte Preset mit einfacher Slot-Zuweisung
    return _generate_fallback_pages(pages_plan, images)


def _generate_fallback_pages(pages_plan: List[PagePlan], images: List[ImageData]) -> List[PageDescription]:
    """Deterministische Fallback-Generierung wenn LLM fehlschlägt."""
    all_presets = load_all_presets()
    fallback = []
    for plan_page in pages_plan:
        preset_id = plan_page.preset_id or "quad_grid"
        preset = all_presets.get(preset_id)
        if preset is None:
            # Fallback: nächstes Preset mit passender Bildanzahl
            count = len(plan_page.image_indices)
            preset_id = get_any_preset(count)
            preset = all_presets.get(preset_id, all_presets["quad_grid"])

        indices = plan_page.image_indices
        image_slots = [s.id for s in preset.slots if s.type == "image"]
        slots = []
        for sid, idx in zip(image_slots, indices):
            slots.append({"slot_id": sid, "image_index": idx})

        # Besserer Fallback-Titel: nutze "purpose" aus dem Plan falls vorhanden
        purpose = plan_page.purpose
        position = plan_page.position
        if purpose and purpose.lower() not in ("cover", "einzelbild", "sammlung", "sequenz", "vergleich"):
            title = purpose[:60]
        elif position == 0:
            title = "Fotobuch"
        else:
            title = f"Seite {position + 1}"
        slots.append({"slot_id": "title", "text": title})

        # Befülle Text-Slots des Presets mit kontextuellen Platzhaltern
        for s in preset.slots:
            if s.type == "text":
                text_role = s.text_role or "caption"
                if text_role == "title":
                    continue  # Titel bereits gesetzt
                elif text_role in ("caption", "intro"):
                    # Nutze vorhandene Bild-Indizes für Kontext
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
