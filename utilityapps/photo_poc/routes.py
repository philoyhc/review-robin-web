"""The photo proof of concept's routes (segment U4;
`utilityapps/guide/segment_U4_photo_poc.md`). Super-admin only, every
response `no-store`.

The page's script posts the original file and the window's rectangle;
`service` does the rest. The two writes take a custom header, which a
cross-site form cannot send without a preflight this host never answers."""

from __future__ import annotations

import re
from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData, UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from cordware.identity import resolve_identity
from utilityapps.access import require_super_admin
from utilityapps.db import get_session
from utilityapps.models import PhotoPocPhoto
from utilityapps.photo_poc import service
from utilityapps.web import templates, url_path

router = APIRouter(prefix="/photo-poc", dependencies=[Depends(require_super_admin)])

DbSession = Annotated[Session, Depends(get_session)]

_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}
#: The header the page's writes carry (see the module docstring).
WRITE_HEADER = "X-Photo-Poc"
# The whole multipart body: the photo plus four small fields and framing.
_BODY_LIMIT = service.MAX_UPLOAD_BYTES + 64 * 1024


def _tile(request: Request, photo: PhotoPocPhoto) -> dict[str, str]:
    created = photo.created_at
    if created.tzinfo is None:  # SQLite hands back naive UTC
        created = created.replace(tzinfo=UTC)
    return {
        "id": photo.public_id,
        "src": url_path(request, f"/photo-poc/photos/{photo.public_id}.jpg"),
        "uploaded_by": photo.uploaded_by,
        "created": created.astimezone(UTC).strftime("%d %b %Y, %H:%M UTC"),
        "size": f"{max(1, round(len(photo.content) / 1024))} KB",
    }


def _refused(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status, headers=_NO_STORE)


@router.get("/", name="utilities_photo_poc")
def page(request: Request, session: DbSession) -> Response:
    width, height = service.OUTPUT_SIZE
    return templates.TemplateResponse(
        request,
        "photo_poc/page.html",
        {
            "max_bytes": service.MAX_UPLOAD_BYTES,
            "max_mb": service.MAX_UPLOAD_BYTES // (1024 * 1024),
            "ratio": service.RATIO,
            "width": width,
            "height": height,
            "write_header": WRITE_HEADER,
            "tiles": [_tile(request, p) for p in service.list_photos(session)],
        },
        headers=_NO_STORE,
    )


# A plain decimal: ASCII digits, an optional sign and fraction, no exponent.
_NUMBER = re.compile(r"-?[0-9]{1,6}(?:\.[0-9]{1,6})?")


def _number(form: FormData, name: str) -> float | None:
    raw = form.get(name)
    if not isinstance(raw, str) or _NUMBER.fullmatch(raw) is None:
        return None
    return float(raw)


@router.post("/photos", name="utilities_photo_poc_save")
async def save(request: Request, session: DbSession) -> Response:
    if request.headers.get(WRITE_HEADER) != "1":
        return _refused(403, "This page's own script saves photos.")
    length = request.headers.get("content-length", "")
    if not length.isdecimal():
        return _refused(411, "The upload did not say its size. Choose the photo again.")
    if len(length) > 18 or int(length) > _BODY_LIMIT:
        return _refused(413, "The photo is larger than 5 MB.")
    try:
        form = await request.form(max_files=1, max_fields=8, max_part_size=_BODY_LIMIT)
    except StarletteHTTPException:
        return _refused(400, "The upload could not be read. Choose the photo again.")
    upload = form.get("photo")
    if not isinstance(upload, UploadFile):
        return _refused(400, "Choose a photo first.")
    data = await upload.read(service.MAX_UPLOAD_BYTES + 1)
    numbers = [_number(form, k) for k in ("cx", "cy", "width", "angle")]
    if any(n is None for n in numbers):
        return _refused(400, "The crop is outside the photo.")
    cx, cy, width, angle = (n for n in numbers if n is not None)
    identity = resolve_identity(request)
    try:
        # Decoding and resizing take a while on a large photo: off the
        # event loop, which every application on the host shares.
        photo = await run_in_threadpool(
            service.save,
            session,
            data,
            service.Frame(cx, cy, width, angle),
            uploaded_by=identity.email or identity.name or "unknown",
        )
    except service.PhotoRefused as exc:
        status = 413 if len(data) > service.MAX_UPLOAD_BYTES else 400
        return _refused(status, str(exc))
    return JSONResponse(_tile(request, photo), status_code=201, headers=_NO_STORE)


@router.get("/photos/{public_id}.jpg", name="utilities_photo_poc_photo")
def photo(request: Request, public_id: str, session: DbSession) -> Response:
    found = service.get(session, public_id)
    if found is None:
        raise StarletteHTTPException(status_code=404)
    etag = f'"{found.sha256}"'
    headers = {"Cache-Control": "private, no-store", "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(found.content, media_type=found.content_type, headers=headers)


@router.delete("/photos/{public_id}", name="utilities_photo_poc_delete")
def delete(request: Request, public_id: str, session: DbSession) -> Response:
    if request.headers.get(WRITE_HEADER) != "1":
        return _refused(403, "This page's own script deletes photos.")
    if not service.delete(session, public_id):
        return _refused(404, "That photo is not there any more.")
    return Response(status_code=204, headers=_NO_STORE)
