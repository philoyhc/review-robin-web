"""Rosters and setup (`/rosters/`): placeholder screens with sample data,
segment 1B item 1. Wired by items 4 and 5."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import Response

from residentialapps.residentialops import sample_data
from residentialapps.residentialops.pages import ROSTER_TABS, placeholders_local_only, render

router = APIRouter(dependencies=[Depends(placeholders_local_only)])

LEVEL_NAME = dict(enumerate(("Unit", *sample_data.LEVEL_LABELS)))

# Setup runs in order (author, 2026-10-27): appointment types and levels,
# then the organization tree, then the rosters. A placeholder previews
# each state with `?stage=`; the wiring items derive it from the data.
STAGES = ("start", "tree", "done")


def _context(request: Request) -> dict[str, Any]:
    stage = request.query_params.get("stage", "done")
    if stage not in STAGES:
        stage = "done"
    return {
        "area": "Rosters",
        "tabs": ROSTER_TABS,
        "sample": sample_data,
        "level_name": LEVEL_NAME,
        "stage": stage,
        "stages": STAGES,
        "tree_open": stage != "start",
        "rosters_open": stage == "done",
        "counts": {level: sum(1 for n in sample_data.TREE if n.level == level) for level in (1, 2, 3)},
        "staff_count": sample_data.linked_count(sample_data.STAFF),
        "ra_count": sample_data.linked_count(sample_data.RAS),
        "post_count": sum(len(node.name.split(", ")) for node in sample_data.TREE),
    }


@router.get("/rosters/", name="residentialops_rosters_home")
def home(request: Request) -> Response:
    return render(request, "residentialops/rosters/home.html", **_context(request))


@router.get("/rosters/organization", name="residentialops_rosters_organization")
def organization(request: Request) -> Response:
    return render(request, "residentialops/rosters/organization.html", **_context(request))


@router.get("/rosters/staff", name="residentialops_rosters_staff")
def staff(request: Request) -> Response:
    context = _context(request)
    return render(request, "residentialops/rosters/staff.html", count=context["staff_count"], **context)


@router.get("/rosters/ras", name="residentialops_rosters_ras")
def ras(request: Request) -> Response:
    context = _context(request)
    return render(request, "residentialops/rosters/ras.html", count=context["ra_count"], **context)
