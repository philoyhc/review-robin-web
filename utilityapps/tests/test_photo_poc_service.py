"""The photo proof of concept's rules (segment U4, rung 3): every refusal,
orientation, the output's size and format, metadata stripped, and keeping
and reading back a photo."""

from __future__ import annotations

import io
from collections.abc import Iterator

import pytest
from PIL import Image, ImageCms
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from utilityapps.db import Base
from utilityapps.photo_poc import service
from utilityapps.photo_poc.service import Crop, PhotoRefused


def _image_bytes(
    size: tuple[int, int] = (800, 1000),
    fmt: str = "JPEG",
    mode: str = "RGB",
    color: object = (200, 30, 60),
    exif: Image.Exif | None = None,
) -> bytes:
    buffer = io.BytesIO()
    image = Image.new(mode, size, color)  # pyright: ignore[reportArgumentType]  -- a test helper's loose color
    options = {"exif": exif} if exif is not None else {}
    image.save(buffer, format=fmt, **options)
    return buffer.getvalue()


FULL = Crop(0, 0, 800, 1000)


def _open(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def test_the_saved_photo_is_a_480_by_600_jpeg() -> None:
    out = _open(service.process(_image_bytes(), FULL))
    assert out.format == "JPEG" and out.size == (480, 600) and out.mode == "RGB"


def test_png_and_webp_are_accepted_and_transparency_lands_on_white() -> None:
    png = _image_bytes(fmt="PNG", mode="RGBA", color=(0, 0, 0, 0))
    out = _open(service.process(png, FULL)).convert("RGB")
    assert out.getpixel((10, 10)) == (255, 255, 255)
    webp = _image_bytes(fmt="WEBP")
    assert _open(service.process(webp, FULL)).size == (480, 600)


def test_the_saved_photo_carries_no_metadata() -> None:
    exif = Image.Exif()
    exif[0x010F] = "Camera maker"  # Make
    exif[0x9003] = "2026:11:12 10:00:00"  # DateTimeOriginal
    data = _image_bytes(exif=exif)
    assert _open(data).getexif()
    out = _open(service.process(data, FULL))
    assert not out.getexif() and "exif" not in out.info and "icc_profile" not in out.info


def test_a_rotated_phone_photo_is_cropped_upright() -> None:
    """Stored 1000 wide by 800 high with orientation 6 (turn 90° clockwise
    to view), it is seen 800 wide by 1000 high, the stored top half on the
    seen right. The browser's rectangle is in the seen pixels."""
    stored = Image.new("RGB", (1000, 800), (0, 0, 255))
    stored.paste((255, 0, 0), (0, 0, 1000, 400))  # stored top half red
    exif = Image.Exif()
    exif[0x0112] = 6
    buffer = io.BytesIO()
    stored.save(buffer, format="JPEG", exif=exif)
    data = buffer.getvalue()

    def centre(crop: Crop) -> tuple[int, ...]:
        pixel = _open(service.process(data, crop)).convert("RGB").getpixel((240, 300))
        assert isinstance(pixel, tuple)
        return pixel

    assert centre(Crop(400, 0, 400, 500))[0] > 200  # seen right: red
    assert centre(Crop(0, 0, 400, 500))[2] > 200  # seen left: blue


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "empty"),
        (b"not a photo at all", "not a photo"),
        (_image_bytes(fmt="GIF", mode="P", color=1), "JPEG, PNG or WebP"),
    ],
)
def test_what_is_not_a_photo_is_refused(data: bytes, message: str) -> None:
    with pytest.raises(PhotoRefused, match=message):
        service.process(data, FULL)


def test_over_5_mb_is_refused() -> None:
    with pytest.raises(PhotoRefused, match="larger than 5 MB"):
        service.process(b"\xff" * (service.MAX_UPLOAD_BYTES + 1), FULL)


def test_a_decompression_bomb_is_refused_before_its_pixels_are_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bomb = _image_bytes(size=(8000, 6000), fmt="PNG", mode="1", color=0)
    assert len(bomb) < service.MAX_UPLOAD_BYTES  # small on disk, 48 Mpx decoded

    def loaded(self: Image.Image) -> None:
        raise AssertionError("the pixels were read")

    monkeypatch.setattr(Image.Image, "load", loaded)
    with pytest.raises(PhotoRefused, match="too many pixels"):
        service.process(bomb, Crop(0, 0, 400, 500))


@pytest.mark.parametrize(
    "crop",
    [
        Crop(-1, 0, 400, 500),
        Crop(0, 0, 0, 0),
        Crop(500, 0, 400, 500),  # past the right edge of 800
        Crop(0, 600, 400, 500),  # past the bottom of 1000
    ],
)
def test_a_crop_outside_the_photo_is_refused(crop: Crop) -> None:
    with pytest.raises(PhotoRefused, match="outside the photo"):
        service.process(_image_bytes(), crop)


def test_a_crop_of_another_shape_is_refused_and_rounding_is_allowed() -> None:
    with pytest.raises(PhotoRefused, match="window's shape"):
        service.process(_image_bytes(), Crop(0, 0, 500, 500))
    # 401 x 500 is a pixel of rounding off 4:5.
    assert _open(service.process(_image_bytes(), Crop(0, 0, 401, 500))).size == (480, 600)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_a_photo_is_kept_listed_read_back_and_deleted(session: Session) -> None:
    first = service.save(session, _image_bytes(), FULL, "admin@example.edu")
    second = service.save(session, _image_bytes(fmt="PNG"), FULL, "admin@example.edu")
    assert first.public_id != second.public_id and len(first.public_id) == 10
    assert [p.public_id for p in service.list_photos(session)] == [
        second.public_id,
        first.public_id,
    ]
    kept = service.get(session, first.public_id)
    assert kept is not None and kept.content_type == "image/jpeg"
    assert _open(kept.content).size == (480, 600) and len(kept.sha256) == 64
    assert service.get(session, "not-an-id") is None
    assert service.delete(session, first.public_id) is True
    assert service.delete(session, first.public_id) is False
    assert service.get(session, first.public_id) is None


def test_a_refused_upload_keeps_nothing(session: Session) -> None:
    with pytest.raises(PhotoRefused):
        service.save(session, b"nope", FULL, "admin@example.edu")
    assert service.list_photos(session) == []


def test_a_jpeg_comment_is_not_carried_into_the_saved_photo() -> None:
    """Codex on #3824: Pillow carries `info` through crop and resize, and
    the JPEG encoder writes an inherited `comment` unless told otherwise."""
    buffer = io.BytesIO()
    Image.new("RGB", (800, 1000), (10, 20, 30)).save(buffer, format="JPEG", comment=b"note")
    saved = _open(service.process(buffer.getvalue(), FULL))
    assert "comment" not in saved.info
    assert b"note" not in service.process(buffer.getvalue(), FULL)


def test_a_color_key_transparent_png_lands_on_white() -> None:
    """Codex on #3824: an RGB PNG whose tRNS chunk marks one color
    transparent is flattened as an alpha channel is."""
    buffer = io.BytesIO()
    Image.new("RGB", (800, 1000), (0, 255, 0)).save(buffer, format="PNG", transparency=(0, 255, 0))
    pixel = _open(service.process(buffer.getvalue(), FULL)).convert("RGB").getpixel((240, 300))
    assert isinstance(pixel, tuple) and min(pixel) > 245


def test_a_phone_jpeg_read_as_mpo_is_accepted() -> None:
    """The cold read: a JPEG with a second picture in an MPF segment opens
    as "MPO"; the first frame is kept."""
    buffer = io.BytesIO()
    first = Image.new("RGB", (800, 1000), (200, 30, 60))
    first.save(buffer, format="MPO", save_all=True, append_images=[Image.new("RGB", (80, 100))])
    assert Image.open(io.BytesIO(buffer.getvalue())).format == "MPO"
    saved = _open(service.process(buffer.getvalue(), FULL)).convert("RGB")
    pixel = saved.getpixel((240, 300))
    assert isinstance(pixel, tuple) and pixel[0] > 180 and pixel[2] < 90


def test_a_color_profile_is_converted_to_srgb_and_not_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cold read: the profile is dropped, so the pixels are converted
    to sRGB first. Pillow builds no Display P3 profile, so the conversion
    is watched rather than measured."""
    srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    buffer = io.BytesIO()
    Image.new("RGB", (800, 1000), (200, 30, 60)).save(buffer, format="JPEG", icc_profile=srgb)
    calls: list[str] = []
    real = ImageCms.profileToProfile

    def watched(image: Image.Image, *args: object, **kwargs: object) -> Image.Image | None:
        calls.append(image.mode)
        return real(image, *args, **kwargs)  # pyright: ignore[reportArgumentType, reportCallIssue]  -- passed through

    monkeypatch.setattr(ImageCms, "profileToProfile", watched)
    saved = _open(service.process(buffer.getvalue(), FULL))
    assert calls == ["RGB"]
    assert "icc_profile" not in saved.info
    pixel = saved.convert("RGB").getpixel((240, 300))
    assert isinstance(pixel, tuple) and abs(pixel[0] - 200) < 8 and abs(pixel[1] - 30) < 8
