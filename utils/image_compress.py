"""Shrink header images that exceed WhatsApp's 5MB image limit.

Used by all three header-image upload paths (template creation, campaign send,
Flows header upload). Images at or under the limit pass through untouched;
larger ones are re-encoded as JPEG at the highest quality that fits.
"""
import io
import logging

from werkzeug.datastructures import FileStorage

logger = logging.getLogger(__name__)

WHATSAPP_IMAGE_MAX_BYTES = 5 * 1024 * 1024   # Meta's limit for JPEG/PNG media
TARGET_MAX_BYTES = int(4.8 * 1024 * 1024)    # headroom under the hard limit
MAX_LONG_SIDE = 2048                         # phones render headers far smaller
QUALITY_STEPS = (90, 87, 84, 81, 78, 75)     # stop at 75 to keep it looking good


class ImageCompressError(Exception):
    """The image is over the limit and could not be brought under it."""


def _mb(n):
    return f"{n / (1024 * 1024):.1f}MB"


def compress_image_bytes(data, content_type=None, filename=None):
    """Return (bytes, content_type, filename, note).

    note is None when the image was already small enough (returned as-is),
    otherwise a human-readable string like 'Image compressed 12.4MB -> 1.8MB'.
    Raises ImageCompressError if the data isn't a readable image or can't be
    brought under the limit.
    """
    if len(data) <= WHATSAPP_IMAGE_MAX_BYTES:
        return data, content_type, filename, None

    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        logger.warning(f"Unreadable image {filename!r}: {e}")
        raise ImageCompressError("Image is over 5MB and could not be read for compression. Use a JPEG or PNG.")

    # Phone photos store rotation in EXIF; bake it in before EXIF is dropped.
    img = ImageOps.exif_transpose(img)

    # JPEG has no alpha: flatten transparency onto white instead of black.
    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
        rgba = img.convert('RGBA')
        bg = Image.new('RGB', rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        img = bg
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    if max(img.size) > MAX_LONG_SIDE:
        img.thumbnail((MAX_LONG_SIDE, MAX_LONG_SIDE), Image.LANCZOS)

    out = None
    for q in QUALITY_STEPS:
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=q, optimize=True, progressive=True)
        out = buf.getvalue()
        if len(out) <= TARGET_MAX_BYTES:
            break
    if out is None or len(out) > TARGET_MAX_BYTES:
        raise ImageCompressError(
            f"Image is {_mb(len(data))} and could not be compressed under 5MB.")

    base = (filename or 'header').rsplit('.', 1)[0] or 'header'
    new_name = f"{base}.jpg"
    note = f"Image compressed {_mb(len(data))} -> {_mb(len(out))}"
    logger.info(f"{note} ({img.size[0]}x{img.size[1]}, q={q}, {filename!r} -> {new_name!r})")
    return out, 'image/jpeg', new_name, note


def compress_image_upload(file_storage):
    """FileStorage in, (FileStorage, note) out. Same pass-through rule as
    compress_image_bytes; the returned object is a fresh FileStorage over the
    compressed bytes (seekable, with matching filename and content_type), so
    callers can hand it to existing upload helpers unchanged."""
    data = file_storage.read()
    file_storage.seek(0)
    new_data, ctype, name, note = compress_image_bytes(
        data, file_storage.content_type, file_storage.filename)
    if note is None:
        return file_storage, None
    return FileStorage(stream=io.BytesIO(new_data), filename=name,
                       content_type=ctype, name=file_storage.name), note
