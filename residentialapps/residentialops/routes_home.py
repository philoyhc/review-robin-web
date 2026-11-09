"""Residential Operations' landing (`/`): choose an application the
viewer reaches (author, 2026-10-28). A placeholder on sample data, drawn
for a sample viewer chosen on the page (`?as=`), segment 1C item 1."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import Response

from residentialapps.residentialops import sample_data
from residentialapps.residentialops.pages import (
    areas_for,
    choices,
    ra_pages_previewers,
    ra_preview_only,
    render,
)

# Previewers, and RA previewers too (author, 2026-11-09).
router = APIRouter(dependencies=[Depends(ra_pages_previewers)])


@router.get("/", name="residentialops_home")
def home(request: Request) -> Response:
    names = [n for n, _ in sample_data.LANDING_VIEWERS]
    # An RA previewer sees the landing as the sample RA, with no viewer to
    # switch to: the others' cards lead to pages they cannot open.
    ra_only = ra_preview_only(request)
    viewer = None if ra_only else request.query_params.get("as")
    viewer = viewer if viewer in names else names[0]
    return render(
        request,
        "residentialops/home.html",
        area="Home",
        areas=areas_for(viewer),
        sample=sample_data,
        me=viewer,
        role=dict(sample_data.LANDING_VIEWERS)[viewer],
        apps=choices(viewer),
        ra_only=ra_only,
    )
