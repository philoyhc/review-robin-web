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
    {"label": "RA Leave", "path": "/ra-leave/admin/"},  # the admin pages first (1C item 1)
    {"label": "RA Events", "path": None},
    {"label": "Rosters", "path": "/rosters/"},
    {"label": "Sys admin", "path": "/sys-admin/"},
)

LEAVE_ADMIN_TABS: tuple[dict[str, str | None], ...] = (
    {"label": "Dashboard", "path": "/ra-leave/admin/"},
    {"label": "Policy", "path": "/ra-leave/admin/policy"},
    {"label": "Entitlements", "path": "/ra-leave/admin/entitlements"},
    {"label": "Approval chain", "path": "/ra-leave/admin/routing"},
    {"label": "Applications", "path": "/ra-leave/admin/applications"},
    {"label": "Appeals", "path": "/ra-leave/admin/appeals"},
)

def leave_ra_tabs(appeals: bool) -> tuple[dict[str, str | None], ...]:
    """An RA's tabs; Extra leave only while appeals are on."""
    return (
        {"label": "Home", "path": "/ra-leave/"},
        {"label": "Apply", "path": "/ra-leave/apply"},
        *(({"label": "Extra leave", "path": "/ra-leave/appeal"},) if appeals else ()),
        {"label": "My cover", "path": "/ra-leave/cover"},
        {"label": "History", "path": "/ra-leave/history"},
    )


def leave_staff_tabs(query: str = "") -> tuple[dict[str, str | None], ...]:
    """A staff member's tabs, carrying the sample viewer (`?as=`)."""
    return tuple(
        {"label": label, "path": path, "query": query}
        for label, path in (
            ("Home", "/ra-leave/staff/"),
            ("Awaiting", "/ra-leave/staff/decide"),
            ("Decided", "/ra-leave/staff/decided"),
            ("Precinct leave", "/ra-leave/staff/precinct"),
        )
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
