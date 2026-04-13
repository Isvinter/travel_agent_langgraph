import gpxpy.geo
from typing import List
from app.state import ImageData

def cluster_images(images: List[ImageData], radius_m=20):
    clusters = []

    for img in images:
        lat, lon = img.latitude, img.longitude
        added = False

        for cluster in clusters:
            dist = gpxpy.geo.distance(lat, lon, 0,
                                      cluster["center_lat"], cluster["center_lon"], 0)
            if dist <= radius_m:
                # zum Cluster hinzufügen
                cluster["images"].append(img)
                # neuen Cluster-Mittelpunkt berechnen
                n = len(cluster["images"])
                cluster["center_lat"] = sum(i.latitude for i in cluster["images"]) / n
                cluster["center_lon"] = sum(i.longitude for i in cluster["images"]) / n
                added = True
                break

        if not added:
            # neues Cluster starten
            clusters.append({
                "center_lat": lat,
                "center_lon": lon,
                "images": [img]
            })

    return clusters