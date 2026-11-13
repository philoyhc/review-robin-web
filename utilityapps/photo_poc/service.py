"""The photo proof of concept's rules (segment U4, rung 3;
`utilityapps/guide/archive/segment_U4_photo_poc.md`, Semantics).

The browser sends the original upload and the window over it, in the
image's own pixels: its center, width and the photo's turn (`Frame`). This
module decodes the upload, applies its EXIF orientation, checks the window
lies inside the photo, cuts out and turns what it shows, resizes it to
480 x 600 and re-encodes a metadata-free JPEG. Only that JPEG is kept: the
bytes stored are always the server's own."""

from __future__ import annotations

import hashlib
import io
import math
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
    """An upload or a window the tool will not keep; the message is the
    user's."""


#: How far a window's corner may fall outside the photo: the browser's
#: rounding, not a margin anyone sees.
SLACK = 1.0
#: The largest turn, either way, in degrees.
MAX_ANGLE = 360.0


@dataclass(frozen=True)
class Frame:
    """The window over the photo, in the oriented image's pixels: its
    center, its width (its height follows from `RATIO`), and the photo's
    turn on screen, in degrees clockwise. At angle 0 the window is the
    axis-aligned rectangle centered on (cx, cy)."""

    cx: float
    cy: float
    width: float
    angle: float = 0.0

    @property
    def height(self) -> float:
        across, down = RATIO
        return self.width * down / across

    def corners(self) -> list[tuple[float, float]]:
        """The window's corners in the photo. The photo is drawn turned
        clockwise by `angle`, so the window lies turned the other way over
        it: a window offset (dx, dy) is the photo offset
        (dx cos a + dy sin a, -dx sin a + dy cos a), y pointing down."""
        a = math.radians(self.angle)
        cos, sin = math.cos(a), math.sin(a)
        w, h = self.width / 2, self.height / 2
        return [
            (self.cx + dx * cos + dy * sin, self.cy - dx * sin + dy * cos)
            for dx, dy in ((-w, -h), (w, -h), (w, h), (-w, h))
        ]


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


def _check(frame: Frame, size: tuple[int, int]) -> None:
    width, height = size
    values = (frame.cx, frame.cy, frame.width, frame.angle)
    if not all(math.isfinite(v) for v in values) or abs(frame.angle) > MAX_ANGLE:
        raise PhotoRefused("The crop is outside the photo.")
    if frame.width < 1:
        raise PhotoRefused("The crop is outside the photo.")
    for x, y in frame.corners():
        if not (-SLACK <= x <= width + SLACK and -SLACK <= y <= height + SLACK):
            raise PhotoRefused("The crop is outside the photo.")


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


def _window(image: Image.Image, frame: Frame) -> Image.Image:
    """What the window shows, at the photo's own resolution, exactly the
    window's size: a piece cut out first, so a large photo is never turned
    whole; that piece turned upright about the window's center; then the
    window cut from it.

    The piece covers both where the window lies over the photo (its
    corners' bounding box) and where the upright window lands after the
    turn (the window's own box about its center): `rotate` keeps the
    canvas's size, so a piece cut to the corners alone is too short for
    the upright window near a quarter turn (cold read, 2026-11-12). The
    piece is not clamped to the photo: `crop` pads beyond it, and no
    padded pixel is inside the window, whose corners `_check` holds over
    the photo."""
    half_w, half_h = frame.width / 2, frame.height / 2
    xs, ys = zip(*frame.corners(), strict=True)
    left = math.floor(min(*xs, frame.cx - half_w)) - 2
    top = math.floor(min(*ys, frame.cy - half_h)) - 2
    right = math.ceil(max(*xs, frame.cx + half_w)) + 2
    bottom = math.ceil(max(*ys, frame.cy + half_h)) + 2
    piece = _flatten(_to_srgb(image.crop((left, top, right, bottom))))
    cx, cy = frame.cx - left, frame.cy - top
    if frame.angle % 360:
        # Pillow turns counterclockwise; the photo was turned clockwise.
        piece = piece.rotate(
            -frame.angle,
            resample=Image.Resampling.BICUBIC,
            center=(cx, cy),
            fillcolor=(255, 255, 255),
        )
    x0, y0 = round(cx - half_w), round(cy - half_h)
    return piece.crop((x0, y0, x0 + round(frame.width), y0 + round(frame.height)))


def process(data: bytes, frame: Frame) -> bytes:
    """The saved JPEG for ``data`` as the window ``frame`` shows it, or
    `PhotoRefused`."""
    image = _open(data)
    _check(frame, image.size)
    # Pillow types `size` with numpy's array type, which is not installed.
    out = _window(image, frame).resize(OUTPUT_SIZE, Image.Resampling.LANCZOS)  # pyright: ignore[reportUnknownMemberType]  -- numpy-typed overload
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


def save(session: Session, data: bytes, frame: Frame, uploaded_by: str) -> PhotoPocPhoto:
    """Process and keep a photo; commits."""
    jpeg = process(data, frame)
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
