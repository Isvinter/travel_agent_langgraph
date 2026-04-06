import matplotlib.pyplot as plt
import gpxpy.geo
from typing import List
from app.services.gpx_analytics import TrackPoint 


def generate_elevation_profile(
    points: List[TrackPoint],
    output_path: str = "elevation_profile.png"
):
    distances = [0.0]  # Start bei 0 km
    elevations = []

    total_distance = 0.0
    prev_point = None

    for point in points:
        if point.elevation is None:
            continue

        if prev_point is not None:
            distance = gpxpy.geo.distance(
                prev_point.lat, prev_point.lon, prev_point.elevation,
                point.lat, point.lon, point.elevation
            ) or 0

            total_distance += distance

        distances.append(total_distance / 1000)  # km
        elevations.append(point.elevation)

        prev_point = point

    # Plot
    plt.figure()
    plt.plot(distances[1:], elevations)  # skip erstes 0
    plt.xlabel("Distance (km)")
    plt.ylabel("Elevation (m)")
    plt.title("Elevation Profile")

    plt.savefig(output_path)
    plt.close()