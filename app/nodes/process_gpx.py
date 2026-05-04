import os

from app.config import OUTPUT_DIR
from app.services.gpx_analytics import analyze_track
from app.services.generate_elevation_profile import generate_elevation_profile
from app.state import AppState


def process_gpx_node(state: AppState) -> AppState:
    """Process GPX file using existing services."""

    gpx_file = state.gpx_file
    print(f"DEBUG: GPX file = {gpx_file}")

    if not gpx_file:
        print("DEBUG: No GPX file provided, returning early")
        return state

    print("DEBUG: Starting GPX analysis...")
    stats, pauses = analyze_track(gpx_file)

    print(f"DEBUG: Analysis complete - distance: {stats.total_distance_m}m")

    # Sicherstellen, dass das Ausgabeverzeichnis existiert
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Elevation-Profil generieren (nicht kritisch — bei Fehler weitermachen)
    elevation_path = os.path.join(OUTPUT_DIR, "elevation_profile.png")
    print(f"DEBUG: Generating elevation profile to {elevation_path}")
    try:
        generate_elevation_profile(stats.points, elevation_path)
        state.elevation_profile_path = elevation_path
        elevation_profile_saved = True
    except Exception as e:
        print(f"⚠️  Elevation profile generation failed: {e} — continuing without it")
        elevation_path = None
        elevation_profile_saved = False

    # State in-place modifizieren (bestehende Felder bleiben erhalten)
    state.gpx_stats = stats
    state.gpx_pauses = pauses
    state.elevation_profile_path = elevation_path
    metadata_update = {
        "file": gpx_file,
        "distance_km": round(stats.total_distance_m / 1000, 2),
        "elevation_gain_m": round(stats.elevation_gain_m, 2),
        "elevation_loss_m": round(stats.elevation_loss_m, 2),
        "avg_speed_kmh": round(stats.avg_speed_kmh, 2),
        "max_speed_kmh": round(stats.max_speed_kmh, 2),
        "total_points": len(stats.points),
        "pauses_count": len(pauses),
    }
    if elevation_profile_saved:
        metadata_update["elevation_profile"] = elevation_path  # type: ignore[arg-type]
    state.metadata.update(metadata_update)

    print("DEBUG: Returning with metadata")
    return state
