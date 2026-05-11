"""LLM Pass 1: Preset-Auswahl (pro Seite ein Preset aus 21 Optionen).

Das LLM wählt für jede Seite ein Preset basierend auf Bildanzahl und Text-Bedarf.
Variety-Regeln im Prompt sorgen für Abwechslung.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from app.config import OLLAMA_BASE_URL
from app.services.ollama_client import call_ollama, strip_thinking_tokens
from app.state import ImageData, WeatherInfo, PhotobookPlan, PagePlan, POI
from app.photobook.presets import get_preset_summary, get_any_preset, get_presets_by_image_count, PhotobookPreset, get_photobook_preset

logger = logging.getLogger(__name__)


# ── Prompt Template ──

PLAN_PROMPT_TEMPLATE = """Du bist Fotobuch-Art-Director fuer eine Wandertour.

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

    return PLAN_PROMPT_TEMPLATE.format(
        context=context,
        page_range_hint=page_range_hint,
        preset_catalog=preset_catalog,
        theme_block=theme_block,
        image_count=image_count,
    )


def _generate_fallback_plan(images: List[ImageData], image_count: int) -> PhotobookPlan:
    """Deterministische Fallback-Planung: chronologische Seiten mit Text-Presets."""
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
    # Wechsle zwischen verschiedenen Presets für Abwechslung im Fallback
    preset_rotation = [
        "single_text_below",
        "double_stacked_text",
        "single_text_left",
        "double_text_right",
        "single_text_below",
    ]
    rotation_idx = 0
    while indices:
        remaining = len(indices)
        if remaining >= 2:
            pid = preset_rotation[rotation_idx % len(preset_rotation)]
            if pid in ("double_stacked_text", "double_text_right"):
                pages.append({
                    "position": pos,
                    "preset_id": pid,
                    "image_indices": [indices.pop(0), indices.pop(0)],
                    "purpose": "Vergleich",
                })
            else:
                pid = "single_text_below"
                pages.append({
                    "position": pos,
                    "preset_id": pid,
                    "image_indices": [indices.pop(0)],
                    "purpose": "Einzelbild",
                })
            rotation_idx += 1
        else:
            pages.append({
                "position": pos,
                "preset_id": "single_text_below",
                "image_indices": [indices.pop(0)],
                "purpose": "Einzelbild",
            })
        pos += 1
    return PhotobookPlan(
        pages=[PagePlan(**p) for p in pages],
    )


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
    poi_list: List[POI],
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
    page_range: str = "",
    preset: Optional[PhotobookPreset] = None,
) -> PhotobookPlan:
    if not images:
        return PhotobookPlan(pages=[])

    if preset is None:
        preset = get_photobook_preset("mixed")

    prompt = _build_plan_prompt(
        len(images), gpx_stats, notes, weather, len(poi_list),
        page_range=page_range if page_range else None,
        preset=preset,
    )

    # Keine Bilder an den Plan-LLM senden — die Layout-Planung ist strukturell
    # (Presets auf Indizes verteilen), nicht inhaltlich.

    plan = None
    try:
        content = call_ollama(
            prompt,
            model=model,
            base_url=base_url,
            temperature=0.3,
            num_predict=32768,
            timeout=300,
        )
        if content:
            content = strip_thinking_tokens(content)
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                plan = json.loads(json_match.group())
                if "pages" in plan and len(plan["pages"]) > 0:
                    if _all_images_used(plan, len(images)):
                        return PhotobookPlan(
                            pages=[PagePlan(**p) for p in plan["pages"]]
                        )
                    else:
                        logger.warning("LLM-Plan verwendet nicht alle Bilder, verwende Fallback")
                else:
                    logger.warning("LLM-Plan hat keine pages, verwende Fallback")
            else:
                logger.warning("Kein JSON-Objekt in LLM-Plan-Antwort, verwende Fallback")
        else:
            logger.warning("LLM-Plan: keine Antwort, verwende Fallback")
    except Exception as e:
        logger.warning("Pass 1 (Planung) fehlgeschlagen: %s", e)
    return _generate_fallback_plan(images, len(images))
