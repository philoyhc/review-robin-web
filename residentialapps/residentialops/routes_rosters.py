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

# Setup runs in order (author, 2026-10-28): the terms, the slots, the
# Staff roster, the RA roster, then the assignments for a term. A
# placeholder previews three states with `?stage=` (`start`: nothing;
# `slots`: terms and slots saved; `done`); the wiring items derive it.
STAGES = ("start", "slots", "done")


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
        "terms_set": stage != "start",
        "slots_open": stage != "start",
        "rosters_open": stage != "start",
        "cells_open": stage == "done",
        "rosters_filled": stage == "done",
        "counts": {
            level: len({getattr(s, attr) for s in sample_data.SLOTS})
            for level, attr in ((1, "wing"), (2, "precinct"), (3, "neighborhood"))
        },
        "staff_count": sample_data.linked_count(sample_data.STAFF),
        "ra_count": sample_data.linked_count(sample_data.RAS),
    }


@router.get("/rosters/", name="residentialops_rosters_home")
def home(request: Request) -> Response:
    return render(request, "residentialops/rosters/home.html", **_context(request))


@router.get("/rosters/assignments", name="residentialops_rosters_assignments")
def assignments(request: Request) -> Response:
    return render(request, "residentialops/rosters/assignments.html", **_context(request))


# The Terms page is a detour, after RRW's `/guide?return_to=`: its back
# link returns to the roster page it was opened from, else Assignments.
RETURN_TO = {tab["path"]: tab["label"] for tab in ROSTER_TABS}


@router.get("/rosters/assignments/terms", name="residentialops_rosters_terms")
def terms(request: Request) -> Response:
    back = request.query_params.get("return_to", "")
    if back not in RETURN_TO:
        back = "/rosters/assignments"
    return render(
        request, "residentialops/rosters/terms.html", back_path=back, back_label=RETURN_TO[back], **_context(request)
    )


@router.get("/rosters/staff", name="residentialops_rosters_staff")
def staff(request: Request) -> Response:
    context = _context(request)
    return render(request, "residentialops/rosters/staff.html", count=context["staff_count"], **context)


@router.get("/rosters/ras", name="residentialops_rosters_ras")
def ras(request: Request) -> Response:
    context = _context(request)
    return render(request, "residentialops/rosters/ras.html", count=context["ra_count"], **context)
