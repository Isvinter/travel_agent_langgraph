"""Content reviewer — single-pass LLM quality gate.

Prüft angereicherte Daten (Wetter, POIs, Bilder) auf thematische Passung
und erstellt einen kuratierten Enrichment-Kontext für den Blog-Prompt.
"""

import json
import re
from typing import Any, Dict, List, Optional

import requests

from app.state import ImageData, WeatherInfo, DailyWeather


OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
MAX_REVIEW_RESPONSE_TOKENS = 2048


def _build_review_prompt(
    weather: Optional[WeatherInfo],
    poi_list: List[Dict[str, Any]],
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
            line = f"{i}. {poi['name']} ({poi.get('type', 'POI')}, {poi.get('distance_km', '?')} km entfernt)"
            if poi.get("wiki_extract"):
                line += f"\n   Wikipedia: {poi['wiki_extract'][:200]}"
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

    # JSON-Extraktion: alles zwischen { und }
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
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
    poi_list: List[Dict[str, Any]],
    selected_images: List[ImageData],
    gpx_stats: Any = None,
    notes: Optional[str] = None,
    model: str = "gemma4:26b-ctx128k",
    base_url: str = "http://localhost:11434",
) -> Dict[str, Any]:
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

    print("🔍 Reviewing enriched content with LLM...")

    try:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": MAX_REVIEW_RESPONSE_TOKENS,
            },
        }
        resp = requests.post(f"{base_url}/api/chat", json=payload, timeout=120)
    except Exception as e:
        print(f"⚠️ Review LLM call failed: {e}")
        return _build_fallback_context(weather, poi_list, selected_images)

    if resp.status_code != 200:
        print(f"⚠️ Review LLM returned {resp.status_code}")
        return _build_fallback_context(weather, poi_list, selected_images)

    content = resp.json().get("message", {}).get("content", "")
    result = _parse_review_response(content)

    if result["coherence_score"] < 3 and result["coherence_score"] > 0:
        print(f"⚠️ Low coherence score ({result['coherence_score']}/10) — continuing anyway")

    # Bilder nach Qualitätsbewertung filtern
    ratings = result.get("image_ratings", {})
    if ratings and selected_images:
        rated = []
        for img in selected_images:
            score = ratings.get(img.path, 3)
            rated.append((score, img))
        rated.sort(key=lambda x: x[0], reverse=True)
        result["filtered_images"] = [img for _, img in rated]
        print(f"🖼️  Images sorted by quality rating (best first)")
    else:
        result["filtered_images"] = list(selected_images)

    kept = len(result.get("kept_pois", []))
    print(f"✅ Review complete: {kept} POIs kept, coherence {result['coherence_score']}/10")
    return result


def _build_fallback_context(
    weather: Optional[WeatherInfo],
    poi_list: List[Dict[str, Any]],
    selected_images: List[ImageData],
) -> Dict[str, Any]:
    """Baut einen Fallback-Kontext, wenn der Review-LLM nicht verfügbar ist."""
    summary = ""
    if weather:
        summary = weather.summary or "Wetterdaten verfügbar (siehe Details)."

    return {
        "kept_pois": poi_list,
        "weather_summary": summary,
        "discarded_weather_fields": [],
        "image_ratings": {img.path: 3 for img in selected_images},
        "filtered_images": list(selected_images),
        "coherence_score": 0,
        "flags": ["review_unavailable"],
    }
