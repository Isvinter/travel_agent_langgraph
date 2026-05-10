"""LLM Pass 2: Slot-Zuweisung + Text innerhalb von Preset-Constraints."""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from app.config import OLLAMA_BASE_URL
from app.services.ollama_client import call_ollama, strip_thinking_tokens
from app.state import ImageData, PageDescription, PhotobookPlan, PagePlan, PageSlot
from app.photobook.preset_loader import load_all_presets
from app.photobook.presets import get_constraint_summary, get_any_preset, get_photobook_preset
from app.photobook.presets import PhotobookPreset
from app.utils.image_utils import encode_image_base64

logger = logging.getLogger(__name__)


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

    # Nur relevante Presets anzeigen
    preset_summary = []
    for pid in sorted(used_preset_ids):
        p = all_presets.get(pid)
        if p:
            slot_info = ", ".join(
                f"{s.id}({s.type},{s.text_role or s.priority or '-'})" for s in p.slots
            )
            preset_summary.append(f"  {pid} [{p.image_count} Bilder, Text={'ja' if p.has_text else 'nein'}]: {slot_info}")
    catalog = "\n".join(preset_summary)

    constraints = get_constraint_summary()

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

    if preset.text_enabled:
        text_required = any(all_presets.get(pid) and all_presets[pid].has_text for pid in used_preset_ids)
        text_block = (
            "TEXT IST PFLICHT: Hat ein Preset Text-Slots, MUSST du diese befuellen. "
            "Lass KEINEN Text-Slot leer. Betrachte die Bilder und beschreibe ausfuehrlich, "
            "was du siehst — Landschaft, Stimmung, Farben, Details, Wetter."
        ) if text_required else ""
    else:
        text_block = ""

    style_block = ""
    if preset.generation_instructions:
        style_block = f"\nSTILVORGABE ({preset.name}): {preset.generation_instructions}\n"

    return f"""Du befuellst die Slots der gewaehlten Presets mit Bildern und ausfuehrlichem Text.

SEITENPLAN (preset_id pro Seite):
{plan_text}

VERWENDETE PRESETS (nur diese sind relevant):
{catalog}
{gpx_text}{notes_text}

{constraints}

{text_block}

AUFGABE PRO SEITE:{style_block}
1. Weise jedem Image-Slot ein Bild zu (image_index aus dem Plan).
2. Text-Rollen: title (stimmungsvoller Titel, 60 Z.), caption (ausfuehrliche Bildbeschreibung, max. 500 Z.), intro (detaillierte Einleitung, max. 1200 Z.).
3. Generiere AUSFUEHRLICHE, lebendige Texte — beschreibe Landschaft, Stimmung, Farben, Details, Wetter, was auf den Bildern zu sehen ist. Nutze die Zeichenlimits WIRKLICH aus.
{"4. JEDE Seite MUSS einen title-Slot haben: {{\"slot_id\": \"title\", \"text\": \"Einzeiliger Seitentitel\"}}" if preset.text_enabled else ""}
{"5. Bei Presets mit MEHREREN Bildern (quad_grid, double_stacked, triple_stacked): beschreibe den Gesamteindruck der Bildgruppe, nicht nur ein einzelnes Bild." if preset.text_enabled else ""}

BEISPIELE:
- cover_hero: [{{"preset_id": "cover_hero", "slots": [{{"slot_id": "title", "text": "Aufbruch im Morgengrauen"}}, {{"slot_id": "main", "image_index": 0}}]}}]
- single_text_below: [{{"preset_id": "single_text_below", "slots": [{{"slot_id": "title", "text": "Alpenwiese"}}, {{"slot_id": "main", "image_index": 1}}, {{"slot_id": "caption", "text": "Ein atemberaubender Weitblick ueber das Tal. Die Morgensonne taucht die gegenüberliegenden Berggipfel in warmes, goldenes Licht. In der Ferne sind vereinzelte Wanderer auf dem schmalen Gratweg zu erkennen, während unter uns die Nebelschwaden langsam aus dem Tal aufsteigen."}}]}}]
- double_stacked (KEIN Text): [{{"preset_id": "double_stacked", "slots": [{{"slot_id": "title", "text": "Aufstieg"}}, {{"slot_id": "top", "image_index": 3}}, {{"slot_id": "bottom", "image_index": 4}}]}}]
- image_text_split: [{{"preset_id": "image_text_split", "slots": [{{"slot_id": "title", "text": "Kapitel 1"}}, {{"slot_id": "image", "image_index": 2}}, {{"slot_id": "text", "text": "Nach drei Stunden stetigen Aufstiegs durch dichten Fichtenwald erreichten wir endlich die Baumgrenze. Vor uns erstreckte sich ein weites Hochplateau, übersät mit bunten Alpenblumen. Der Wind frischte auf und trug den Duft von wildem Thymian heran. Wir legten eine wohlverdiente Rast ein und genossen den ersten unverstellten Blick auf die gegenüberliegende Gipfelkette, deren schroffe Zacken sich scharf gegen den tiefblauen Himmel abzeichneten."}}]}}]

ANTWORTE NUR mit JSON-Array:"""


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
            num_predict=16384,
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
