"""Residential Operations' landing (`/`): choose an application the
viewer reaches (author, 2026-10-28). A placeholder on sample data, drawn
for a sample viewer chosen on the page (`?as=`), segment 1C item 1."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import Response

from residentialapps.residentialops import sample_data
from residentialapps.residentialops.pages import areas_for, choices, placeholders_local_only, render

router = APIRouter(dependencies=[Depends(placeholders_local_only)])


@router.get("/", name="residentialops_home")
def home(request: Request) -> Response:
    names = [n for n, _ in sample_data.LANDING_VIEWERS]
    viewer = request.query_params.get("as")
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
    )
