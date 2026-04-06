import gpxpy
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class TrackPoint(BaseModel):
    lat: float
    lon: float
    elevation: Optional[float]
    time: Optional[datetime]


class GPXStats(BaseModel):
    total_distance_m: float
    elevation_gain_m: float
    elevation_loss_m: float
    avg_speed_kmh: float
    max_speed_kmh: float
    points: List[TrackPoint]


# ---------------------------
# 1. PARSING
# ---------------------------
def parse_gpx(gpx_track: str) -> List[TrackPoint]:
    with open(gpx_track, "r", encoding="utf-8") as f:
        gpx = gpxpy.parse(f)

    points: List[TrackPoint] = []

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                points.append(
                    TrackPoint(
                        lat=point.latitude,
                        lon=point.longitude,
                        elevation=point.elevation,
                        time=point.time,
                    )
                )

    return points


# ---------------------------
# 2. ANALYTICS
# ---------------------------
def compute_gpx_stats(points: List[TrackPoint]) -> GPXStats:
    total_distance = 0.0
    elevation_gain = 0.0
    elevation_loss = 0.0
    max_speed = 0.0
    total_time = 0.0

    MAX_SPEED_KMH = 50.0
    MAX_DISTANCE_PER_STEP = 1000.0  # optional glitch filter

    prev_point: Optional[TrackPoint] = None

    for point in points:
        if prev_point is None:
            prev_point = point
            continue

        # distance
        try:
            distance = gpxpy.geo.distance(
                prev_point.lat,
                prev_point.lon,
                prev_point.elevation,
                point.lat,
                point.lon,
                point.elevation,
            )
        except Exception:
            prev_point = point
            continue

        if distance is None or distance > MAX_DISTANCE_PER_STEP:
            prev_point = point
            continue

        total_distance += distance

        # elevation
        if point.elevation is not None and prev_point.elevation is not None:
            diff = point.elevation - prev_point.elevation
            if diff > 0:
                elevation_gain += diff
            else:
                elevation_loss += abs(diff)

        # speed
        if point.time and prev_point.time:
            time_diff = (point.time - prev_point.time).total_seconds()

            if time_diff > 0:
                speed = distance / time_diff
                speed_kmh = speed * 3.6

                if speed_kmh < MAX_SPEED_KMH:
                    max_speed = max(max_speed, speed)
                    total_time += time_diff

        prev_point = point

    avg_speed = (total_distance / 1000) / (total_time / 3600) if total_time > 0 else 0

    return GPXStats(
        total_distance_m=total_distance,
        elevation_gain_m=elevation_gain,
        elevation_loss_m=elevation_loss,
        avg_speed_kmh=avg_speed,
        max_speed_kmh=max_speed * 3.6,
        points=points,
    )


#---------------------------
# PAUSE DETECTION
#---------------------------
def detect_pauses(
    points: List[TrackPoint],
    min_pause_minutes: float = 10.0,
    distance_threshold_m: float = 20.0,
) -> List[dict]:

    pauses = []

    pause_start_time = None
    pause_start_point = None

    prev_point = None

    for point in points:
        if point.time is None:
            continue

        if prev_point is None:
            prev_point = point
            continue

        if prev_point.time is None:
            prev_point = point
            continue

        # distance + time
        distance = gpxpy.geo.distance(
            prev_point.lat, prev_point.lon, prev_point.elevation,
            point.lat, point.lon, point.elevation
        ) or 0

        time_diff = (point.time - prev_point.time).total_seconds()

        if time_diff <= 0:
            prev_point = point
            continue

        # 🟢 FALL 1: kaum Bewegung → evtl. Pause
        if distance < distance_threshold_m:
            if pause_start_time is None:
                pause_start_time = prev_point.time
                pause_start_point = prev_point

        # 🔴 FALL 2: Bewegung → Pause evtl. beenden
        else:
            if pause_start_time is not None:
                duration_sec = (prev_point.time - pause_start_time).total_seconds()
                duration_min = duration_sec / 60

                if duration_min >= min_pause_minutes:
                    pauses.append({
                        "start_time": pause_start_time,
                        "end_time": prev_point.time,
                        "duration_minutes": round(duration_min, 2),
                        "location": {
                            "lat": pause_start_point.lat,
                            "lon": pause_start_point.lon,
                        },
                    })

                pause_start_time = None
                pause_start_point = None

        prev_point = point

    return pauses


def analyze_track(gpx_track: str) -> tuple[GPXStats, List[dict]]:
    """
    Main function to parse a GPX file, compute stats, and detect pauses.
    """
    points = parse_gpx(gpx_track)
    stats = compute_gpx_stats(points)
    pauses = detect_pauses(points)

    return stats, pauses

# ---------------------------
# 3. WRAPPER
# ---------------------------
def gpx_analytics(gpx_track: str) -> GPXStats:
    points = parse_gpx(gpx_track)
    return compute_gpx_stats(points)