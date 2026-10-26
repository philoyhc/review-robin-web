"""Rosters and setup (`/rosters/`): placeholder screens with sample data,
segment 1B item 1. Wired by items 4 and 5."""

from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import Response

from residentialapps.ops import sample_data
from residentialapps.ops.pages import ROSTER_TABS, render

router = APIRouter()

LEVEL_NAME = dict(enumerate(("Unit", *sample_data.LEVEL_LABELS)))


@router.get("/rosters/", name="residentialops_rosters_organization")
def organization(request: Request) -> Response:
    tree = sample_data.TREE
    return render(
        request,
        "ops/rosters/organization.html",
        area="Rosters",
        tabs=ROSTER_TABS,
        sample=sample_data,
        counts={level: sum(1 for n in tree if n.level == level) for level in (1, 2, 3)},
        staff_count=sample_data.linked_count(sample_data.STAFF),
        ra_count=sample_data.linked_count(sample_data.RAS),
        level_name=LEVEL_NAME,
    )


@router.get("/rosters/staff", name="residentialops_rosters_staff")
def staff(request: Request) -> Response:
    return render(
        request,
        "ops/rosters/staff.html",
        area="Rosters",
        tabs=ROSTER_TABS,
        sample=sample_data,
        count=sample_data.linked_count(sample_data.STAFF),
        level_name=LEVEL_NAME,
    )


@router.get("/rosters/ras", name="residentialops_rosters_ras")
def ras(request: Request) -> Response:
    return render(
        request,
        "ops/rosters/ras.html",
        area="Rosters",
        tabs=ROSTER_TABS,
        sample=sample_data,
        count=sample_data.linked_count(sample_data.RAS),
        level_name=LEVEL_NAME,
    )
