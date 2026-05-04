# app/services/poi_enricher.py
"""POI enrichment via Overpass API + optional Wikipedia extracts.

Kostenlos, kein API-Key, keine Registrierung.
Findet Points of Interest in der Nähe von Pause-Orten entlang der Route.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import json
import math
from pathlib import Path
import time

import requests


OVERPASS_INSTANCES = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

OVERPASS_POI_CATEGORIES = {
    "natural": [
        "peak", "volcano", "cliff", "cave_entrance", "rock",
        "spring", "waterfall", "glacier", "ridge", "valley",
        "saddle", "hill", "geyser", "crater",
    ],
    "tourism": [
        "alpine_hut", "wilderness_hut", "viewpoint", "picnic_site",
        "camp_site", "artwork", "attraction", "guest_house",
    ],
    "historic": [
        "castle", "ruins", "memorial", "wayside_cross",
        "archaeological_site", "boundary_stone", "battlefield",
        "mine", "monument", "city_gate", "fort", "tower",
    ],
    "amenity": [
        "shelter", "drinking_water", "fountain", "bench",
        "hunting_stand", "biergarten",
    ],
    "leisure": [
        "picnic_table", "firepit",
    ],
    "man_made": [
        "cross", "tower", "observatory", "cairn",
    ],
    "waterway": ["waterfall", "dam"],
    "water": ["lake", "reservoir"],
}

DEFAULT_SEARCH_RADIUS_M = 2000
MAX_POIS_PER_LOCATION = 15
PROXIMITY_DEDUP_M = 500

POI_CACHE_PATH = Path("output/poi_cache.json")

MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]  # Sekunden


def _get_cache_key(lat: float, lon: float, radius: int) -> str:
    """Erzeugt einen Cache-Key aus Koordinaten und Radius."""
    return f"{lat:.4f}_{lon:.4f}_{radius}"


def _load_cache(cache_path: Path = POI_CACHE_PATH) -> Dict[str, Any]:
    """Lädt den POI-Cache aus der JSON-Datei."""
    try:
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Cache-Datei konnte nicht geladen werden: {e}")
    return {}


def _save_to_cache(key: str, pois: List[Dict[str, Any]], cache_path: Path = POI_CACHE_PATH):
    """Speichert POIs für einen Key im Cache."""
    try:
        cache = _load_cache(cache_path)
        cache[key] = pois
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Cache konnte nicht gespeichert werden: {e}")


def _try_overpass_query(query: str) -> Optional[List[Dict[str, Any]]]:
    """Sendet eine Overpass-Query mit Retry und Instanz-Fallback.

    Probiert alle Instanzen mit exponentiellem Backoff.
    Gibt None zurück wenn keine Instanz erreichbar ist.
    """
    request_headers = {
        "Content-Type": "text/plain",
        "Accept": "application/json",
        "User-Agent": "TravelBlogBot/1.0",
    }

    for attempt in range(MAX_RETRIES + 1):
        instance_idx = attempt % len(OVERPASS_INSTANCES)
        url = OVERPASS_INSTANCES[instance_idx]

        try:
            resp = requests.post(
                url,
                data=query.encode("utf-8"),
                headers=request_headers,
                timeout=30,
            )
        except Exception as e:
            print(f"⚠️ Overpass {url} nicht erreichbar: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
            continue

        if resp.status_code == 200:
            try:
                return resp.json().get("elements", [])
            except Exception:
                print(f"⚠️ Ungültiges JSON von {url}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
                continue

        print(f"⚠️ Overpass {url} antwortete mit {resp.status_code}")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])

    return None


def _build_overpass_query(lat: float, lon: float, radius: int = DEFAULT_SEARCH_RADIUS_M) -> str:
    """Baut eine Overpass QL-Query aus den Kategorien in OVERPASS_POI_CATEGORIES."""
    lines = ["[out:json];", "("]

    for category, values in OVERPASS_POI_CATEGORIES.items():
        value_str = "|".join(values)
        # Nodes
        lines.append(
            f'  node["{category}"~"{value_str}"](around:{radius},{lat},{lon});'
        )
        # Ways (für Flächen-POIs wie Seen, Burganlagen, etc.)
        lines.append(
            f'  way["{category}"~"{value_str}"](around:{radius},{lat},{lon});'
        )

    lines.append(");")
    lines.append(f"out center {MAX_POIS_PER_LOCATION};")
    return "\n".join(lines)


def _parse_overpass_response(
    data: Dict[str, Any],
    ref_lat: float,
    ref_lon: float,
) -> List[Dict[str, Any]]:
    """Parst Overpass JSON-Antwort in POI-Dicts mit Distanzberechnung."""
    results = []
    for element in data.get("elements", []):
        tags = element.get("tags", {})

        # POI-Typ bestimmen — alle Kategorien aus OVERPASS_POI_CATEGORIES prüfen
        poi_type = "unknown"
        for tag_key in OVERPASS_POI_CATEGORIES:
            if tag_key in tags:
                poi_type = tags[tag_key]
                break

        if poi_type == "unknown":
            continue

        # Koordinaten: nodes direkt, ways über center
        if element.get("type") == "node":
            el_lat = element.get("lat", ref_lat)
            el_lon = element.get("lon", ref_lon)
        elif element.get("type") == "way":
            center = element.get("center", {})
            el_lat = center.get("lat", ref_lat)
            el_lon = center.get("lon", ref_lon)
        else:
            continue

        name = tags.get("name", f"{poi_type} ({el_lat:.3f}, {el_lon:.3f})")

        # Distanz berechnen (Haversine-Approximation)
        dlat = math.radians(el_lat - ref_lat)
        dlon = math.radians(el_lon - ref_lon)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(ref_lat)) * math.cos(math.radians(el_lat)) *
             math.sin(dlon / 2) ** 2)
        distance_km = 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        poi = {
            "name": name,
            "type": poi_type,
            "lat": el_lat,
            "lon": el_lon,
            "distance_km": round(distance_km, 2),
        }

        wiki_tag = tags.get("wikipedia")
        if wiki_tag:
            poi["wiki_tag"] = wiki_tag

        results.append(poi)

    return results


def _deduplicate_pois_by_name_and_proximity(pois: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Entfernt doppelte POIs nach Name und räumlicher Nähe."""
    if not pois:
        return []

    kept: List[Dict[str, Any]] = []
    seen_names = set()

    for poi in pois:
        name_lower = poi["name"].lower()

        # Name-Dedup
        if name_lower in seen_names:
            continue

        # Nähe-Dedup: zu nah an einem bereits behaltenen POI?
        too_close = False
        for existing in kept:
            dist = math.sqrt(
                ((poi["lat"] - existing["lat"]) * 111.32 * 1000) ** 2 +
                ((poi["lon"] - existing["lon"]) * 111.32 *
                 math.cos(math.radians(poi["lat"])) * 1000) ** 2
            )
            if dist < PROXIMITY_DEDUP_M:
                too_close = True
                break

        if not too_close:
            kept.append(poi)
            seen_names.add(name_lower)

    return kept


def _enrich_with_wikipedia(poi: Dict[str, Any]) -> Dict[str, Any]:
    """Reichert einen POI mit dem Wikipedia-Lead-Paragraph an (optional)."""
    wiki_tag = poi.get("wiki_tag")
    if not wiki_tag:
        return poi

    # wikipedia=de:Berggipfel -> lang=de, title=Berggipfel
    parts = wiki_tag.split(":", 1)
    if len(parts) != 2:
        return poi
    lang, title = parts

    try:
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            extract = data.get("extract", "")
            if extract:
                result = {**poi, "wiki_extract": extract[:500]}
                return result
    except Exception as e:
        print(f"⚠️ Wikipedia fetch failed for {wiki_tag}: {e}")
    return poi


def fetch_pois(
    pauses: List[dict],
    search_radius_m: int = DEFAULT_SEARCH_RADIUS_M,
) -> List[Dict[str, Any]]:
    """Findet Points of Interest in der Nähe der Pause-Orte.

    Args:
        pauses: Liste von Pause-Dicts mit location.lat/lon
        search_radius_m: Suchradius um jede Pause in Metern

    Returns:
        Liste von POI-Dicts mit name, type, lat, lon, distance_km, wiki_extract
    """
    if not pauses:
        print("⚠️ Keine Pausen-Daten — POI-Suche nicht möglich")
        return []

    all_pois: List[Dict[str, Any]] = []
    cache = _load_cache()

    for pause in pauses:
        loc = pause.get("location", {})
        lat, lon = loc.get("lat"), loc.get("lon")
        if lat is None or lon is None:
            continue

        cache_key = _get_cache_key(lat, lon, search_radius_m)

        # Cache-Check
        if cache_key in cache:
            all_pois.extend(cache[cache_key])
            continue

        query = _build_overpass_query(lat, lon, search_radius_m)
        elements = _try_overpass_query(query)
        if elements:
            pois = _parse_overpass_response({"elements": elements}, lat, lon)
            _save_to_cache(cache_key, pois)
            cache[cache_key] = pois
            all_pois.extend(pois)
        else:
            print(f"⚠️ Keine POI-Daten für ({lat}, {lon})")

    # Deduplizieren
    all_pois = _deduplicate_pois_by_name_and_proximity(all_pois)

    # Mit Wikipedia-Texten anreichern (für POIs mit wiki-Tag)
    enriched = [_enrich_with_wikipedia(poi) for poi in all_pois]

    print(f"📍 Found {len(enriched)} unique POIs near {len(pauses)} pause locations")
    return enriched
