# app/services/poi_enricher.py
"""POI enrichment via Overpass API + optional Wikipedia extracts.

Kostenlos, kein API-Key, keine Registrierung.
Findet Points of Interest in der Nähe von Pause-Orten entlang der Route.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import math
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


def _build_overpass_query(lat: float, lon: float, radius: int = DEFAULT_SEARCH_RADIUS_M) -> str:
    """Baut eine Overpass QL-Query für POIs um eine Koordinate."""
    return f"""[out:json];
(
  node["tourism"~"viewpoint|alpine_hut|information|museum"](around:{radius},{lat},{lon});
  node["natural"="peak"](around:{radius},{lat},{lon});
  node["historic"~"ruins|castle|memorial"](around:{radius},{lat},{lon});
);
out {MAX_POIS_PER_LOCATION};"""


def _parse_overpass_response(
    data: Dict[str, Any],
    ref_lat: float,
    ref_lon: float,
) -> List[Dict[str, Any]]:
    """Parst Overpass JSON-Antwort in POI-Dicts mit Distanzberechnung."""
    results = []
    for element in data.get("elements", []):
        if element.get("type") not in ("node", "way"):
            continue
        tags = element.get("tags", {})

        # POI-Typ bestimmen
        poi_type = "unknown"
        for tag_key in ("tourism", "natural", "historic"):
            if tag_key in tags:
                poi_type = tags[tag_key]
                break
        if poi_type == "unknown" and element.get("type") == "node":
            continue

        el_lat = element.get("lat", ref_lat)
        el_lon = element.get("lon", ref_lon)
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

        # Wikipedia-Tag extrahieren falls vorhanden
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

    for pause in pauses:
        loc = pause.get("location", {})
        lat, lon = loc.get("lat"), loc.get("lon")
        if lat is None or lon is None:
            continue

        query = _build_overpass_query(lat, lon, search_radius_m)

        try:
            resp = requests.post(
                OVERPASS_URL,
                data=query.encode("utf-8"),
                headers={"Content-Type": "text/plain"},
                timeout=60,
            )
        except Exception as e:
            print(f"⚠️ Overpass API nicht erreichbar für ({lat}, {lon}): {e}")
            continue

        if resp.status_code == 429:
            print("⚠️ Overpass rate limit — warte 2 Sekunden und versuche erneut")
            time.sleep(2)
            try:
                resp = requests.post(
                    OVERPASS_URL,
                    data=query.encode("utf-8"),
                    headers={"Content-Type": "text/plain"},
                    timeout=60,
                )
            except Exception:
                continue

        if resp.status_code != 200:
            print(f"⚠️ Overpass antwortete mit {resp.status_code}")
            continue

        try:
            data = resp.json()
        except Exception:
            continue

        pois = _parse_overpass_response(data, lat, lon)
        all_pois.extend(pois)

    # Deduplizieren
    all_pois = _deduplicate_pois_by_name_and_proximity(all_pois)

    # Mit Wikipedia-Texten anreichern (für POIs mit wiki-Tag)
    enriched = [_enrich_with_wikipedia(poi) for poi in all_pois]

    print(f"📍 Found {len(enriched)} unique POIs near {len(pauses)} pause locations")
    return enriched
