"""Gemeinsam genutzte Bildverarbeitungs-Funktionen.

Wird sowohl von der Blog- als auch der Photobuch-Pipeline verwendet.
"""

import base64 as _b64
import io
import io as _io
import os


def compress_image_to_jpeg(
    image_path: str,
    output_path: str,
    max_size_bytes: int = 1024 * 1024,  # 1 MB
    max_dim: int = 1200,
) -> str | None:
    """Komprimiert ein Bild auf ≤ max_size_bytes, konvertiert nach JPEG.

    Resizet zuerst auf max_dim, reduziert dann JPEG-Qualität.
    Bei Bedarf wird weiter verkleinert bis das Limit erreicht ist.
    Gibt den Pfad zur ausgegebenen Datei zurück oder None bei Fehler.
    """
    try:
        from PIL import Image, ImageOps

        if not os.path.exists(image_path):
            return None

        with Image.open(image_path) as img:
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")  # JPEG unterstützt kein Alpha/Kanäle

            # Mandatory: auf max_dim runterskalieren
            if max(img.size) > max_dim:
                ratio = max_dim / max(img.size)
                img = img.resize(
                    (int(img.width * ratio), int(img.height * ratio)),
                    Image.LANCZOS,
                )

            w, h = img.size

            # Phase 1: JPEG-Qualität reduzieren
            quality = 85
            while quality >= 10:
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)
                if len(buf.getvalue()) <= max_size_bytes:
                    with open(output_path, "wb") as f:
                        f.write(buf.getvalue())
                    return output_path
                quality -= 5

            # Phase 2: weitere Grössenreduktion
            while max(w, h) > 200:
                w = int(w * 0.75)
                h = int(h * 0.75)
                resized = img.resize((w, h), Image.LANCZOS)

                buf = io.BytesIO()
                resized.save(buf, format="JPEG", quality=75, optimize=True)
                if len(buf.getvalue()) <= max_size_bytes:
                    with open(output_path, "wb") as f:
                        f.write(buf.getvalue())
                    return output_path

            # Fallback: kleinste mögliche Größe
            buf = io.BytesIO()
            img.resize((200, int(h * 200 / w))).save(
                buf, format="JPEG", quality=10, optimize=True
            )
            with open(output_path, "wb") as f:
                f.write(buf.getvalue())
            return output_path

    except Exception as e:
        print(f"⚠️ Error compressing image {image_path}: {e}")
        return None


def encode_image_base64(image_path: str, max_size: int = 800, quality: int = 85) -> str | None:
    """Encodiert ein Bild als Base64-String für multimodale LLM-Requests.

    Args:
        image_path: Pfad zum Bild
        max_size: Maximale Breite/Höhe für Thumbnail (Default 800)
        quality: JPEG-Qualität 1-100 (Default 85)

    Returns:
        Base64-encoded string oder None bei Fehler
    """
    try:
        from PIL import Image

        if not os.path.exists(image_path):
            return None

        with Image.open(image_path) as img:
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size))

            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            buf = _io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=quality)
            return _b64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"⚠️ Error encoding image {image_path}: {e}")
        return None
