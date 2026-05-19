"""Orientierungserkennung für Bilder (Landscape/Portrait/Square)."""
import logging

from PIL import Image

logger = logging.getLogger(__name__)


def get_orientation(image_path: str) -> str:
    """Ermittelt die Bildorientierung.

    Verwendet PIL Image.open() und EXIF-Orientierungs-Tag.
    Gibt 'landscape', 'portrait' oder 'square' zurück.
    """
    try:
        img = Image.open(image_path)
        # EXIF Orientation Tag (0x0112) prüfen
        exif = img.getexif()
        if exif:
            orientation = exif.get(0x0112, 1)
            # Orientierungen 5-8 bedeuten 90°/270° gedreht → vertauscht Breite/Höhe
            if orientation in (5, 6, 7, 8):
                w, h = img.size[1], img.size[0]
            else:
                w, h = img.size
        else:
            w, h = img.size

        if w > h:
            return "landscape"
        elif h > w:
            return "portrait"
        return "square"
    except Exception:
        logger.warning("Orientierungserkennung fehlgeschlagen für %s", image_path, exc_info=True)
        return "landscape"  # Fallback: meistens Querformat


def get_orientations(image_paths: list[str]) -> list[str]:
    """Ermittelt Orientierungen für eine Liste von Bildpfaden."""
    return [get_orientation(p) for p in image_paths]
