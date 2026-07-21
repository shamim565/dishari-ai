import io

from PIL import Image, UnidentifiedImageError

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_EDGE = 1600

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "TIFF", "GIF"}


class UnsupportedImage(Exception):
    pass


def normalize_ticket_image(raw_bytes):
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise UnsupportedImage("too_large")
    try:
        image = Image.open(io.BytesIO(raw_bytes))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise UnsupportedImage("unreadable") from exc

    if image.format not in ALLOWED_FORMATS:
        raise UnsupportedImage("format")

    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    image.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue(), "image/jpeg"
