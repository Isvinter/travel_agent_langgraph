"""Content reviewer — single-pass LLM quality gate.

Prüft angereicherte Daten (Wetter, POIs, Bilder) auf thematische Passung
und erstellt einen kuratierten Enrichment-Kontext für den Blog-Prompt.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.config import OLLAMA_BASE_URL
from app.services.ollama_client import call_ollama
from app.state import ImageData, WeatherInfo, POI, EnrichmentContext

logger = logging.getLogger(__name__)


OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
MAX_REVIEW_RESPONSE_TOKENS = 2048


def _extract_json_object(text: str) -> Optional[str]:
    """Extrahiert das erste vollständige JSON-Objekt aus Text mit verschachtelten Klammern."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _build_review_prompt(
    weather: Optional[WeatherInfo],
    poi_list: List[POI],
    selected_images: List[ImageData],
    gpx_stats_d: Optional[Dict[str, Any]],
    notes: Optional[str],
) -> str:
    """Baut den Review-Prompt für das LLM."""

    # Wetter-Sektion
    weather_text = ""
    if weather and weather.daily:
        weather_text = weather.summary
        if not weather_text:
            lines = []
            for dw in weather.daily:
                parts = f"{dw.date}: {dw.temperature_min:.0f}–{dw.temperature_max:.0f}°C"
                if dw.precipitation_mm > 0:
                    parts += f", {dw.precipitation_mm:.1f}mm Regen ({dw.precipitation_hours}h)"
                if dw.freezing_level_m is not None:
                    parts += f", 0°C-Grenze bei {dw.freezing_level_m:.0f}m"
                if dw.cloud_cover_pct > 50:
                    parts += f", {dw.cloud_cover_pct:.0f}% bewölkt"
                parts += f", {dw.wind_speed_kmh:.0f} km/h Wind"
                lines.append(parts)
            weather_text = "\n".join(lines)
    else:
        weather_text = "Keine Wetterdaten verfügbar."

    # GPX-Stats
    gpx_text = ""
    if gpx_stats_d:
        parts = []
        if gpx_stats_d.get("total_distance_m"):
            parts.append(f"Distanz: {gpx_stats_d['total_distance_m']/1000:.1f} km")
        if gpx_stats_d.get("elevation_gain_m"):
            parts.append(f"Höhenmeter: {gpx_stats_d['elevation_gain_m']:.0f} m auf")
        points = gpx_stats_d.get("points", [])
        if points:
            elevations = [p.get("elevation", 0) or 0 for p in points if p.get("elevation")]
            if elevations:
                max_elev = max(elevations)
                parts.append(f"Maximale Höhe: {max_elev:.0f} m")
        gpx_text = "\n".join(parts)
    if not gpx_text:
        gpx_text = "Keine GPX-Daten verfügbar."

    notes_text = notes if notes else "Keine Notizen verfügbar."

    # POI-Sektion
    if poi_list:
        poi_lines = []
        for i, poi in enumerate(poi_list):
            line = f"{i}. {poi.name} ({getattr(poi, 'type', 'POI')}, {getattr(poi, 'distance_km', '?')} km entfernt)"
            if getattr(poi, "wiki_extract", None):
                line += f"\n   Wikipedia: {poi.wiki_extract[:200]}"
            poi_lines.append(line)
        poi_text = "\n".join(poi_lines)
    else:
        poi_text = "Keine POIs gefunden."

    # Bilder-Sektion
    if selected_images:
        img_lines = []
        for i, img in enumerate(selected_images):
            loc = ""
            if img.latitude and img.longitude:
                loc = f"({img.latitude:.4f}, {img.longitude:.4f})"
            ts = img.timestamp or "kein Zeitstempel"
            img_lines.append(f"{i}. {img.path} — {ts} {loc}")
        image_text = "\n".join(img_lines)
    else:
        image_text = "Keine Bilder ausgewählt."

    prompt = f"""You are a travel blog editor. Review the following enriched trip data.
Your job is to filter and curate for a compelling narrative.

WETTERDATEN:
{weather_text}

TOUR-STATISTIKEN:
{gpx_text}

NOTIZEN ZUR TOUR:
{notes_text}

POINTS OF INTEREST ({len(poi_list)} gefunden):
{poi_text}

AUSGEWÄHLTE BILDER ({len(selected_images)} Bilder):
{image_text}

AUFGABEN:
1. POI-Filterung: Markiere jeden POI als KEEP oder DISCARD. Verwerfe irrelevante
   Einträge (urbane Infrastruktur, banale Orte, Duplikate nach Name/Nähe).
   Behalte maximal 8 POIs. Gib einen kurzen Grund für jedes DISCARD an.
2. Wetter-Kontext: Schreibe eine 2-3 sätzige Wetter-Zusammenfassung für die Blog-Einleitung.
   Verwende die maximale Höhe aus den Tour-Statistiken, um zu beurteilen, ob die
   0°C-Grenze relevant ist.
   WICHTIG — manche Wetterfelder sind kontextabhängig und MÜSSEN verworfen werden, wenn
   sie nicht relevant sind:
   - Niederschlagsdaten (Menge + Stunden): verwerfen, wenn die Tour kaum oder keinen
     Niederschlag hatte.
   - 0°C-Grenze (freezing_level): verwerfen, wenn die maximale Höhe der Tour weit darunter
     liegt (z.B. 0°C-Grenze bei 2500 m bei einer flachen 200 m-Wanderung). Nur behalten,
     wenn sie innerhalb von ~1000 m der maximalen Track-Höhe liegt oder alpines Gelände betroffen ist.
   - Windgeschwindigkeit: verwerfen bei unauffälligen Werten (< 20 km/h).
   Ziel: den Blog-Schreiber NICHT mit irrelevanten Daten verwirren.
3. Bildqualität: Bewerte jedes Bild 1-5 auf thematische Eignung für einen Reiseblog.
   Markiere Bilder, die unscharf, schlecht komponiert oder Duplikate sein könnten.
4. Gesamtkohärenz: Vergib 1-10 Punkte, wie gut die Daten eine Geschichte erzählen.

Antworte AUSSCHLIESSLICH als gültiges JSON:
{{"pois": [{{"name": "...", "action": "KEEP|DISCARD", "reason": "..."}}],
 "weather_summary": "...",
 "discarded_weather_fields": [],
 "image_ratings": {{"pfad/zum/bild.jpg": 4}},
 "coherence_score": 7,
 "flags": ["image_x_blurry", "poi_y_irrelevant"]}}"""

    return prompt


def _parse_review_response(response: Optional[str]) -> Dict[str, Any]:
    """Parst die LLM-Antwort — JSON mit Regex-Fallback."""
    default: Dict[str, Any] = {
        "kept_pois": [],
        "weather_summary": "",
        "discarded_weather_fields": [],
        "image_ratings": {},
        "coherence_score": 0,
        "flags": [],
    }

    if not response:
        return default

    # JSON-Extraktion: finde das erste { mit passender schließender }
    json_str = _extract_json_object(response)
    if json_str:
        try:
            data = json.loads(json_str)
            result = {
                "kept_pois": [p for p in data.get("pois", []) if p.get("action") == "KEEP"],
                "weather_summary": data.get("weather_summary", ""),
                "discarded_weather_fields": data.get("discarded_weather_fields", []),
                "image_ratings": data.get("image_ratings", {}),
                "coherence_score": data.get("coherence_score", 0),
                "flags": data.get("flags", []),
            }
            return result
        except json.JSONDecodeError:
            pass

    # Fallback: gesamte Antwort als Weather Summary
    default["weather_summary"] = response[:500]
    default["coherence_score"] = 0
    return default


def review_enrichment(
    weather: Optional[WeatherInfo],
    poi_list: List[POI],
    selected_images: List[ImageData],
    gpx_stats: Any = None,
    notes: Optional[str] = None,
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
) -> EnrichmentContext:
    """Führt die Content-Review durch und gibt kuratierten Kontext zurück.

    Args:
        weather: WeatherInfo oder None
        poi_list: Liste der POI-Dicts
        selected_images: Ausgewählte Bilder
        gpx_stats: GPXStats-Objekt
        notes: Tour-Notizen
        model: Ollama-Modellname
        base_url: Ollama API URL

    Returns:
        Dict mit kept_pois, weather_summary, discarded_weather_fields,
        image_ratings, coherence_score, flags
    """
    # GPX-Stats serialisieren für den Prompt
    gpx_d = None
    if gpx_stats is not None:
        if hasattr(gpx_stats, "model_dump"):
            gpx_d = gpx_stats.model_dump()
        elif isinstance(gpx_stats, dict):
            gpx_d = gpx_stats

    prompt = _build_review_prompt(
        weather=weather,
        poi_list=poi_list,
        selected_images=selected_images,
        gpx_stats_d=gpx_d,
        notes=notes,
    )

    logger.info("Reviewing enriched content with LLM...")

    content = call_ollama(
        prompt,
        model=model,
        base_url=base_url,
        temperature=0.3,
        top_p=None,
        num_predict=MAX_REVIEW_RESPONSE_TOKENS,
        timeout=300,
    )
    if content is None:
        return _build_fallback_context(weather, poi_list, selected_images)

    result = _parse_review_response(content)

    if result["coherence_score"] < 3 and result["coherence_score"] > 0:
        logger.warning("Low coherence score (%s/10) — continuing anyway", result['coherence_score'])

    # Bilder nach Qualitätsbewertung filtern
    ratings = result.get("image_ratings", {})
    if ratings and selected_images:
        rated = []
        for img in selected_images:
            score = ratings.get(img.path, 3)
            rated.append((score, img))
        rated.sort(key=lambda x: x[0], reverse=True)
        filtered_images = [img for _, img in rated]
        logger.info("Images sorted by quality rating (best first)")
    else:
        filtered_images = list(selected_images)

    # LLM-kept_pois auf originale POI-Objekte zurückmappen
    kept_poi_names = {p.get("name", "") for p in result.get("kept_pois", [])}
    kept_pois = [p for p in poi_list if p.name in kept_poi_names]

    kept = len(kept_pois)
    logger.info("Review complete: %s POIs kept, coherence %s/10", kept, result['coherence_score'])

    return EnrichmentContext(
        weather_summary=result.get("weather_summary", ""),
        kept_pois=kept_pois,
        discarded_weather_fields=result.get("discarded_weather_fields", []),
        image_ratings=result.get("image_ratings", {}),
        filtered_images=filtered_images,
        coherence_score=result.get("coherence_score", 0),
        flags=result.get("flags", []),
    )


def _build_fallback_context(
    weather: Optional[WeatherInfo],
    poi_list: List[POI],
    selected_images: List[ImageData],
) -> EnrichmentContext:
    """Baut einen Fallback-Kontext, wenn der Review-LLM nicht verfügbar ist."""
    summary = ""
    if weather:
        summary = weather.summary or "Wetterdaten verfügbar (siehe Details)."

    return EnrichmentContext(
        kept_pois=poi_list,
        weather_summary=summary,
        discarded_weather_fields=[],
        image_ratings={img.path: 3 for img in selected_images},
        filtered_images=list(selected_images),
        coherence_score=0,
        flags=["review_unavailable"],
    )
