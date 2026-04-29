"""Generate synthetic test images with EXIF GPS metadata.

Run once: uv run python tests/fixtures/generate_images.py
"""
from PIL import Image
import piexif
import os


def create_exif_jpeg(output_path, lat, lon, datetime_str, color=(255, 0, 0)):
    """Create a 200x200 solid-color JPEG with embedded GPS EXIF."""
    img = Image.new("RGB", (200, 200), color)

    zeroth_ifd = {}
    exif_ifd = {}

    def to_rational(val):
        d = int(val)
        m = int((val - d) * 60)
        s = int(((val - d) * 60 - m) * 60 * 100)
        return ((d, 1), (m, 1), (s, 100))

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: 'N' if lat >= 0 else 'S',
        piexif.GPSIFD.GPSLatitude: to_rational(abs(lat)),
        piexif.GPSIFD.GPSLongitudeRef: 'E' if lon >= 0 else 'W',
        piexif.GPSIFD.GPSLongitude: to_rational(abs(lon)),
    }

    dt = datetime_str.replace("-", ":").replace("T", " ")
    exif_ifd[piexif.ExifIFD.DateTimeOriginal] = dt

    exif_dict = {
        "0th": zeroth_ifd,
        "Exif": exif_ifd,
        "GPS": gps_ifd,
    }

    exif_bytes = piexif.dump(exif_dict)
    img.save(output_path, "JPEG", exif=exif_bytes)
    print(f"Created: {output_path}")


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))

    create_exif_jpeg(
        os.path.join(base, "images", "photo_a.jpg"),
        lat=47.3, lon=8.5,
        datetime_str="2025-06-01T10:00:00",
        color=(200, 50, 50),
    )

    create_exif_jpeg(
        os.path.join(base, "images", "photo_b.jpg"),
        lat=47.30015, lon=8.50015,  # ~15m from photo_a
        datetime_str="2025-06-01T10:02:00",
        color=(50, 200, 50),
    )

    create_exif_jpeg(
        os.path.join(base, "images", "photo_c.jpg"),
        lat=47.5, lon=9.0,  # far away, separate cluster
        datetime_str="2025-06-01T11:00:00",
        color=(50, 50, 200),
    )
