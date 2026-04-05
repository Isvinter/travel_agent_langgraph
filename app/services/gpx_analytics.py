import gpxpy
from pydantic import BaseModel

class GPXStats(BaseModel):
    total_distance_m: float
    elevation_gain_m: float
    elevation_loss_m: float
    avg_speed_kmh: float
    max_speed_kmh: float


def gpx_analytics(gpx_track: str) -> GPXStats:

    with open(gpx_track, "r", encoding="utf-8") as f:
        gpx = gpxpy.parse(f)

    total_distance = 0
    elevation_gain = 0
    elevation_loss = 0
    max_speed = 0
    total_time = 0

    MAX_SPEED_KMH = 50

    for track in gpx.tracks:
        for segment in track.segments:
            prev_point = None

            for point in segment.points:
                if prev_point is None:
                    prev_point = point
                    continue

                distance = prev_point.distance_3d(point)
                total_distance += distance

                # elevation
                if point.elevation and prev_point.elevation:
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

    return {
        "total_distance_m": total_distance,
        "elevation_gain_m": elevation_gain,
        "elevation_loss_m": elevation_loss,
        "avg_speed_kmh": avg_speed,
        "max_speed_kmh": max_speed * 3.6,
    }