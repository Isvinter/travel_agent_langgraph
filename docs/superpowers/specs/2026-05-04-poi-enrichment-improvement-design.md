# POI Enrichment Improvement Design

**Datum:** 2026-05-04
**Status:** approved

## Problem

Overpass API liefert flächendeckend HTTP 406 auf alle POI-Anfragen. Zusätzlich sind die POI-Kategorien mit nur 8 Tags stark limitiert.

## Ziel

Robuste, fehlertolerante POI-Abfrage mit breiter Kategorieabdeckung für Outdoor-Touren. Kostenlos, kein API-Key.

## Design

### 1. API-Robustheit (Fix für HTTP 406)

Die 406-Fehler entstehen wahrscheinlich durch Überlastung (Overpass gibt bei hoher Last oft 406 statt 429). Aktuell wird nur 429 explizit behandelt.

**Änderungen:**

- **Mehrere Overpass-Instanzen** als Fallback:
  1. `https://overpass-api.de/api/interpreter` (primär)
  2. `https://overpass.kumi.systems/api/interpreter`
  3. `https://maps.mail.ru/osm/tools/overpass/api/interpreter`
- **Headers setzen:** `User-Agent: TravelBlogBot/1.0` und `Accept: application/json`
- **Generischer Retry:** Bei JEDEM Nicht-200-Status (nicht nur 429) → bis zu 3 Retries mit exponentiellem Backoff (1s, 2s, 4s). Bei jedem Retry nächste Instanz verwenden.
- **Timeout:** 30s (statt 60s) für schnellere Failover.

### 2. Erweiterte POI-Kategorien

Statt 8 fest kodierter Tags → ~60 outdoor-relevante Kategorien:

```python
OVERPASS_POI_CATEGORIES = {
    # Natur
    "natural": [
        "peak", "volcano", "cliff", "cave_entrance", "rock",
        "spring", "waterfall", "glacier", "ridge", "valley",
        "saddle", "hill", "geyser", "crater",
    ],
    # Tourismus
    "tourism": [
        "alpine_hut", "wilderness_hut", "viewpoint", "picnic_site",
        "camp_site", "artwork", "attraction", "guest_house",
    ],
    # Historisch
    "historic": [
        "castle", "ruins", "memorial", "wayside_cross",
        "archaeological_site", "boundary_stone", "battlefield",
        "mine", "monument", "city_gate", "fort", "tower",
    ],
    # Rast/Schutz
    "amenity": [
        "shelter", "drinking_water", "fountain", "bench",
        "hunting_stand", "biergarten",
    ],
    # Freizeiteinrichtungen
    "leisure": [
        "picnic_table", "firepit",
    ],
    # Bauwerke
    "man_made": [
        "cross", "tower", "observatory", "cairn",
    ],
    # Gewässer
    "waterway": ["waterfall", "dam"],
    "water": ["lake", "reservoir"],
}
```

Query wird dynamisch aus dem Dict gebaut. Zusätzlich `way`-Elemente abfragen (nicht nur `node`). Schwerpunkt der Way-Mitte wird als Referenzpunkt genutzt. Limit pro Ort: 15 POIs (vorher 10).

### 3. POI-Cache (Dateibasiert)

Einfaches JSON-Cache unter `output/poi_cache.json`:

```json
{
  "47.3_11.4_2000": [
    {"name": "Berggipfel", "type": "peak", ...},
    ...
  ]
}
```

Key-Format: `{lat}_{lon}_{radius}`. Bei wiederholten Pipeline-Runs mit gleicher Route werden keine API-Calls verschwendet. Cache-Einträge werden bei erfolgreicher API-Antwort geschrieben.

### 4. Keine neuen Abhängigkeiten

Alles bleibt bei `requests` + Standardbibliothek. Kein SQLite, kein Redis, keine neuen Packages.

## Betroffene Dateien

| Datei | Änderung |
|---|---|
| `app/services/poi_enricher.py` | Hauptänderung: Retry-Logik, Instanz-Failover, erweiterte Kategorien, Cache |
| `app/nodes/enrich_poi_node.py` | Keine Änderung nötig (Interface bleibt gleich) |
| `tests/test_services/test_poi_enricher.py` | Tests für neue Kategorien, Retry, Cache, Fallback-Instanzen |
| `tests/test_nodes/test_enrich_poi.py` | Keine Änderung nötig (Interface bleibt gleich) |

## Nicht im Scope

- Nominatim, Wikipedia-Geosearch, Google Places (kann später ergänzt werden)
- Lokale OSM-Datenbank (Overkill für aktuellen Use Case)
- POI-Bewertungen, Öffnungszeiten (brauchen kostenpflichtige APIs)
- Cache-Invalidierung / TTL (YAGNI — Cache kann manuell gelöscht werden)
