"""Residential Operations' page rendering: its templates and the chrome's
context (`residentialapps/spec/residentialops_ui.md` §2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from cordware.identity import current_identity, is_local
from residentialapps.residentialops import sample_data
from residentialapps.web.urls import templates

TEMPLATES = templates([Path(__file__).resolve().parent / "templates"])

APP_NAME = "Residential Operations"

# The switcher's areas; a path of None is an area not built yet.
AREAS: tuple[dict[str, str | None], ...] = (
    {"label": "Home", "path": None},
    {"label": "RA Leave", "path": None},
    {"label": "RA Events", "path": None},
    {"label": "Rosters", "path": "/rosters/"},
    {"label": "Sys admin", "path": "/sys-admin/"},
)

ROSTER_TABS: tuple[dict[str, str | None], ...] = (
    {"label": "Home", "path": "/rosters/"},
    {"label": "Assignments", "path": "/rosters/assignments"},
    {"label": "Staff roster", "path": "/rosters/staff"},
    {"label": "RA roster", "path": "/rosters/ras"},
)


def placeholders_local_only() -> None:
    """Segment 1B item 1's screens show sample data and enforce no
    access rules yet, so they answer only on a local run (`APP_ENV=local`).
    Deployed, they are 404 until items 3–5 wire them to real data and
    gates; a router depends on this until then."""
    if not is_local():
        raise HTTPException(status_code=404)


def _initials(label: str) -> str:
    parts = [p for p in label.replace("@", " ").split() if p[:1].isalpha()]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def render(
    request: Request,
    template: str,
    *,
    area: str,
    tabs: tuple[dict[str, str | None], ...] = (),
    areas: tuple[dict[str, str | None], ...] = AREAS,
    **context: Any,
) -> Response:
    viewer = current_identity(request)
    return TEMPLATES.TemplateResponse(
        request,
        template,
        {
            "app_key": "residentialops",
            "app_name": APP_NAME,
            "unit_name": sample_data.UNIT_NAME,
            "area": area,
            "areas": areas,
            "tabs": tabs,
            "viewer": viewer,
            "initials": _initials(viewer.display_label) if viewer else "?",
            **context,
        },
    )
