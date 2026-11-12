"""The photo proof of concept's page (segment U4, rung 4: the scaffold).
Super-admin only, every response `no-store`. The controls are inert and
the saved-photos list shows sample tiles until rung 5 wires them."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import Response

from utilityapps.access import require_super_admin
from utilityapps.photo_poc import service
from utilityapps.web import templates

router = APIRouter(prefix="/photo-poc", dependencies=[Depends(require_super_admin)])

_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}

# The scaffold's sample tiles: what a saved photo's tile will carry.
SAMPLE_TILES = (
    {"uploaded_by": "admin@example.edu", "created": "12 Nov 2026, 14:05", "size": "64 KB"},
    {"uploaded_by": "admin@example.edu", "created": "12 Nov 2026, 13:52", "size": "81 KB"},
    {"uploaded_by": "admin@example.edu", "created": "12 Nov 2026, 13:40", "size": "57 KB"},
)


@router.get("/", name="utilities_photo_poc")
def page(request: Request) -> Response:
    width, height = service.OUTPUT_SIZE
    return templates.TemplateResponse(
        request,
        "photo_poc/page.html",
        {
            "max_mb": service.MAX_UPLOAD_BYTES // (1024 * 1024),
            "ratio": service.RATIO,
            "width": width,
            "height": height,
            "tiles": SAMPLE_TILES,
        },
        headers=_NO_STORE,
    )
