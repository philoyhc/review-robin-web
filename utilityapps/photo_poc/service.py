"""The photo proof of concept's rules (segment U4, rung 3;
`utilityapps/guide/segment_U4_photo_poc.md`, Semantics).

The browser sends the original upload and the window's rectangle in the
image's own pixels; this module decodes the upload, applies its EXIF
orientation, checks the rectangle, crops, resizes to 480 x 600 and
re-encodes a metadata-free JPEG. Only that JPEG is kept: the bytes stored
are always the server's own."""

from __future__ import annotations

import hashlib
import io
import secrets
from dataclasses import dataclass

from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from utilityapps.models import PhotoPocPhoto

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
#: The window's shape, width : height, and the saved size (author, 2026-11-12).
RATIO = (4, 5)
OUTPUT_SIZE = (480, 600)
#: Decoded size refused beyond this, before the pixels are read: a
#: decompression bomb is a small file that decodes to a huge image.
MAX_PIXELS = 40_000_000
# Pillow reads a phone JPEG carrying more than one picture (a depth map or
# HDR gain map, in an MPF segment) as "MPO"; its first frame is the photo.
ACCEPTED_FORMATS = frozenset({"JPEG", "MPO", "PNG", "WEBP"})
JPEG_QUALITY = 85
CONTENT_TYPE = "image/jpeg"

# A public ID in RRW's alphabet (look-alikes left out), copied rather than
# imported: Utilities may not import another application.
_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"
_ID_LENGTH = 10


class PhotoRefused(ValueError):
    """An upload or a rectangle the tool will not keep; the message is the
    user's."""


@dataclass(frozen=True)
class Crop:
    """The window's rectangle, in the oriented image's pixels."""

    x: int
    y: int
    width: int
    height: int


def _open(data: bytes) -> Image.Image:
    if not data:
        raise PhotoRefused("The file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise PhotoRefused("The photo is larger than 5 MB.")
    try:
        image = Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise PhotoRefused("The file is not a photo this tool can read.") from exc
    if image.format not in ACCEPTED_FORMATS:
        raise PhotoRefused("Choose a JPEG, PNG or WebP photo.")
    if image.width * image.height > MAX_PIXELS:
        raise PhotoRefused("The photo has too many pixels to process.")
    try:
        image.load()
    except (OSError, ValueError, SyntaxError) as exc:
        raise PhotoRefused("The file is not a photo this tool can read.") from exc
    return ImageOps.exif_transpose(image)


def _check(crop: Crop, size: tuple[int, int]) -> None:
    width, height = size
    if crop.width < 1 or crop.height < 1 or crop.x < 0 or crop.y < 0:
        raise PhotoRefused("The crop is outside the photo.")
    if crop.x + crop.width > width or crop.y + crop.height > height:
        raise PhotoRefused("The crop is outside the photo.")
    across, down = RATIO
    # Within a pixel of rounding either way: |w * 5 - h * 4| <= 5.
    if abs(crop.width * down - crop.height * across) > max(RATIO):
        raise PhotoRefused("The crop is not the window's shape.")


def _flatten(image: Image.Image) -> Image.Image:
    """RGB, with any transparency on white."""
    # An alpha channel, or a palette or color key marked transparent
    # (`transparency` in `info`, e.g. a PNG's tRNS chunk).
    if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


# Pillow's stubs leave `createProfile`'s return partly untyped; wrapped,
# it is a typed profile.
_SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]  -- partly untyped stub


def _to_srgb(image: Image.Image) -> Image.Image:
    """The pixels in sRGB when the upload carries a color profile (an
    iPhone's Display P3, say): the saved file carries none, so a browser
    reads it as sRGB. Without a profile, or one this cannot apply, the
    pixels are taken as sRGB already."""
    icc = image.info.get("icc_profile")
    if not isinstance(icc, bytes) or not icc or image.mode not in ("RGB", "RGBA", "CMYK"):
        return image
    try:
        source = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        converted = ImageCms.profileToProfile(
            image, source, _SRGB, outputMode="RGBA" if image.mode == "RGBA" else "RGB"
        )
    except (ImageCms.PyCMSError, OSError, ValueError):
        return image
    return image if converted is None else converted


def process(data: bytes, crop: Crop) -> bytes:
    """The saved JPEG for ``data`` cropped to ``crop``, or `PhotoRefused`."""
    image = _open(data)
    _check(crop, image.size)
    box = (crop.x, crop.y, crop.x + crop.width, crop.y + crop.height)
    cropped = _flatten(_to_srgb(image.crop(box)))
    # Pillow types `size` with numpy's array type, which is not installed.
    out = cropped.resize(OUTPUT_SIZE, Image.Resampling.LANCZOS)  # pyright: ignore[reportUnknownMemberType]  -- numpy-typed overload
    # Pillow carries the upload's `info` (a JPEG comment, DPI, ...) through
    # crop and resize, and the JPEG encoder writes some of it by default.
    out.info.clear()
    buffer = io.BytesIO()
    # No `exif=` and no `icc_profile=`: the saved file carries no metadata.
    out.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue()


def _new_public_id(session: Session) -> str:
    while True:
        candidate = "".join(secrets.choice(_ALPHABET) for _ in range(_ID_LENGTH))
        if get(session, candidate) is None:
            return candidate


def save(session: Session, data: bytes, crop: Crop, uploaded_by: str) -> PhotoPocPhoto:
    """Process and keep a photo; commits."""
    jpeg = process(data, crop)
    photo = PhotoPocPhoto(
        public_id=_new_public_id(session),
        uploaded_by=uploaded_by,
        content_type=CONTENT_TYPE,
        width=OUTPUT_SIZE[0],
        height=OUTPUT_SIZE[1],
        sha256=hashlib.sha256(jpeg).hexdigest(),
        content=jpeg,
    )
    session.add(photo)
    session.commit()
    return photo


def get(session: Session, public_id: str) -> PhotoPocPhoto | None:
    if len(public_id) != _ID_LENGTH or any(c not in _ALPHABET for c in public_id):
        return None
    return session.execute(
        select(PhotoPocPhoto).where(PhotoPocPhoto.public_id == public_id)
    ).scalar_one_or_none()


def list_photos(session: Session) -> list[PhotoPocPhoto]:
    """Every saved photo, newest first."""
    return list(
        session.execute(
            select(PhotoPocPhoto).order_by(PhotoPocPhoto.created_at.desc(), PhotoPocPhoto.id.desc())
        ).scalars()
    )


def delete(session: Session, public_id: str) -> bool:
    """Delete a photo; whether one was there. Commits."""
    photo = get(session, public_id)
    if photo is None:
        return False
    session.delete(photo)
    session.commit()
    return True
