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


# ---------------------------
# 3. WRAPPER
# ---------------------------
def gpx_analytics(gpx_track: str) -> GPXStats:
    points = parse_gpx(gpx_track)
    return compute_gpx_stats(points)