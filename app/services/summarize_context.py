"""Tour-Summary-Service: Erzeugt kompakte Tour-Zusammenfassung via LLM."""

import logging
from typing import Optional
from app.services.ollama_client import call_ollama

logger = logging.getLogger(__name__)

PRESET_TOUR_TYPE = {
    "nature_outdoor": "Wanderung",
    "nature_collage": "Naturtour",
    "culture_architecture": "Städtetrip",
    "people": "Gruppenausflug",
    "mixed": "Tour",
}

SUMMARIZE_PROMPT = """Erstelle eine kurze Zusammenfassung dieser Tour (max. 150 Wörter).
Enthalte: Tourtyp (Wanderung/Radtour/Städtetrip), Region/Gebiet,
Jahreszeit, besonderer Anlass (falls erkennbar).
Keine detaillierten Wegbeschreibungen.

TOURDATEN: {distance}km, {elevation}m Aufstieg
TOURNOTIZEN: {notes}"""


def _build_summary_prompt(
    notes: Optional[str],
    distance_km: Optional[float],
    elevation_m: Optional[float],
) -> str:
    dist_str = f"{distance_km:.1f}" if distance_km is not None else "?"
    elev_str = f"{elevation_m:.0f}" if elevation_m is not None else "?"
    notes_str = notes if notes else "Keine Notizen vorhanden."
    return SUMMARIZE_PROMPT.format(distance=dist_str, elevation=elev_str, notes=notes_str)


def _build_fallback_summary(
    distance_km: Optional[float],
    elevation_m: Optional[float],
    preset: str,
) -> str:
    tour_type = PRESET_TOUR_TYPE.get(preset, "Tour")
    parts = []
    if distance_km is not None:
        parts.append(f"{distance_km:.1f}km")
    parts.append(tour_type)
    if elevation_m is not None and elevation_m > 0:
        parts.append(f"mit {elevation_m:.0f}m Aufstieg")
    return " ".join(parts) + "."


def summarize_context(
    notes: Optional[str],
    gpx_distance_km: Optional[float],
    gpx_elevation_m: Optional[float],
    preset: str,
    model: str = "gemma4:26b-ctx128k",
) -> str:
    prompt = _build_summary_prompt(notes, gpx_distance_km, gpx_elevation_m)
    try:
        content = call_ollama(
            prompt,
            model=model,
            temperature=0.0,
            num_predict=1024,
            timeout=60,
            disable_thinking=True,
        )
        if content and content.strip():
            return content.strip()
    except Exception as e:
        logger.warning("Summarize-LLM fehlgeschlagen: %s", e)

    return _build_fallback_summary(gpx_distance_km, gpx_elevation_m, preset)
