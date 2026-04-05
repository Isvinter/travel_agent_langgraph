from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS


def convert_to_decimal_degrees(value, ref):
    def to_float(r):
        try:
            return float(r)
        except Exception:
            return r[0] / r[1]

    degrees = to_float(value[0])
    minutes = to_float(value[1])
    seconds = to_float(value[2])

    decimal = degrees + minutes / 60 + seconds / 3600

    if isinstance(ref, bytes):
        ref = ref.decode()

    if ref in ["S", "W"]:
        decimal = -decimal

    return decimal


def extract_gps(gps_raw):
    gps_data = {}

    for gps_tag_id, gps_value in gps_raw.items():
        gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
        gps_data[gps_tag] = gps_value

    result = {
        "latitude": None,
        "longitude": None,
    }

    if "GPSLatitude" in gps_data and "GPSLatitudeRef" in gps_data:
        result["latitude"] = convert_to_decimal_degrees(
            gps_data["GPSLatitude"],
            gps_data["GPSLatitudeRef"],
        )

    if "GPSLongitude" in gps_data and "GPSLongitudeRef" in gps_data:
        result["longitude"] = convert_to_decimal_degrees(
            gps_data["GPSLongitude"],
            gps_data["GPSLongitudeRef"],
        )

    return result


def extract_metadata(image_path):
    image = Image.open(image_path)
    exif_data = image._getexif()

    metadata = {
        "timestamp": None,
        "latitude": None,
        "longitude": None,
    }

    if not exif_data:
        return metadata

    for tag_id, value in exif_data.items():
        tag = TAGS.get(tag_id, tag_id)

        if tag == "DateTimeOriginal":
            metadata["timestamp"] = value

        elif tag == "GPSInfo":
            gps = extract_gps(value)
            metadata.update(gps)

    return metadata