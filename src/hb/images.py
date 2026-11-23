"""Save a picked photo into the app's folder, shrunk to save data and storage."""
from __future__ import annotations

import io
import os

from . import config
from .store import new_id

MAX_SIDE = 1600
QUALITY = 75


def _shrink(data: bytes) -> bytes:
    try:
        from PIL import Image, ImageOps
    except ImportError:  # Pillow missing: keep the original
        return data
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        out = io.BytesIO()
        img.save(out, "JPEG", quality=QUALITY, optimize=True)
        return out.getvalue() if out.tell() < len(data) else data
    except Exception:
        return data


def save_photo(family_id: str, data: bytes) -> tuple[str, str]:
    """Returns (storage_path, local_path). storage_path is '<family_id>/<id>.jpg'."""
    storage_path = f"{family_id}/{new_id()}.jpg"
    local = os.path.join(config.DATA_DIR, "images", storage_path)
    os.makedirs(os.path.dirname(local), exist_ok=True)
    with open(local, "wb") as f:
        f.write(_shrink(data))
    return storage_path, local
