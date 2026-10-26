"""Rosters and setup (`/rosters/`): placeholder screens with sample data,
segment 1B item 1. Wired by items 4 and 5."""

from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import Response

from residentialapps.ops import sample_data
from residentialapps.ops.pages import ROSTER_TABS, render

router = APIRouter()


@router.get("/rosters/", name="residentialops_rosters_organization")
def organization(request: Request) -> Response:
    tree = sample_data.TREE
    counts = {level: sum(1 for n in tree if n.level == level) for level in (1, 2, 3)}
    return render(
        request,
        "ops/rosters/organization.html",
        area="Rosters",
        tabs=ROSTER_TABS,
        sample=sample_data,
        counts=counts,
        level_name=dict(enumerate(("Unit", *sample_data.LEVEL_LABELS))),
    )
