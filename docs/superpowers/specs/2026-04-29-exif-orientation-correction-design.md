# EXIF Orientation Correction in Image Compression

## Purpose

Smartphone cameras often store EXIF orientation metadata instead of physically rotating the image. When Pillow processes such images without applying the orientation transform, the output appears rotated (typically 90, 180, or 270 degrees). This change ensures compressed output images have the correct orientation.

## Architecture

**Location:** `app/services/blog_generator.py`, function `compress_image_to_jpeg()`

**Change:** Add one call to `ImageOps.exif_transpose()` immediately after `Image.open()`, before `img.convert("RGB")`.

```
Before:                                After:
Image.open(path)                       Image.open(path)
img.convert("RGB")                     ImageOps.exif_transpose(img)  ← NEW
                                       img.convert("RGB")
```

## Approach

Use Pillow's built-in `PIL.ImageOps.exif_transpose()`, which reads the EXIF Orientation tag (0x0112) and applies the correct rotation/flip automatically. This handles all 8 EXIF orientation values.

## Data Flow

```
Selected images → compress_image_to_jpeg()
  → Image.open(path)
  → ImageOps.exif_transpose(img)   ← orientation correction
  → img.convert("RGB")
  → resize to max_dim (1200px)
  → JPEG compression (quality + size reduction loops)
  → write to output/{timestamp}/images/
```

## Error Handling

`ImageOps.exif_transpose()` is a no-op when:
- No EXIF data exists (scanned image, screenshot)
- No Orientation tag is present (default orientation = 1)
- File is PNG, GIF, or BMP (no EXIF orientation support)

No try/except wrapping needed — it is safe on all input types.

## Edge Cases

| Case | Behavior |
|------|----------|
| Correctly oriented image (orientation=1) | No-op, image unchanged |
| Image without EXIF metadata | No-op, image unchanged |
| PNG, GIF, BMP images | No-op, image unchanged |
| RGBA/LA/P mode images | Orientation applied first, then `convert("RGB")` |
| Corrupt EXIF data | Pillow returns the image unmodified |

## Scope

**Modified:**
- `app/services/blog_generator.py` — `compress_image_to_jpeg()`: add `ImageOps.exif_transpose()` call
- `app/services/blog_generator.py` — imports: add `ImageOps` to the `from PIL import` line

**Not modified:**
- `encode_image_to_base64()` — out of scope
- `image_selector.py` — out of scope
- Pipeline graph — no new node
- AppState — no new fields
- No new dependencies (Pillow already provides `ImageOps`)

## Testing

No test framework changes needed. Manual verification:
1. Run the full pipeline with test images that have non-default EXIF orientation
2. Verify output images in `output/{timestamp}/images/` are correctly oriented
