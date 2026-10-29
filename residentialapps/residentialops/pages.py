"""Residential Operations' page rendering: its templates and the chrome's
context (`residentialapps/spec/residentialops_ui.md` §2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from cordware.identity import current_identity, is_local
from residentialapps.residentialops import sample_data, sample_leave
from residentialapps.web.urls import templates

TEMPLATES = templates([Path(__file__).resolve().parent / "templates"])

APP_NAME = "Residential Operations"

# The switcher's areas for a sys admin, the default; a path of None is an
# area not built yet. A sample viewer's menu is `areas_for` theirs.
AREAS: tuple[dict[str, str | None], ...] = (
    {"label": "Home", "path": "/"},
    {"label": "RA Leave admin", "path": "/ra-leave/admin/"},
    {"label": "RA Events", "path": None},
    {"label": "Rosters and setup", "path": "/rosters/"},
    {"label": "Sys admin", "path": "/sys-admin/"},
)

def choices(viewer: str) -> list[dict[str, str]]:
    """The applications a sample viewer reaches, each at its own entry
    point: RA Leave's RA, staff or admin side by who they are; Rosters and
    Sys admin for sys admins only (the landing's cards)."""
    is_ra = any(ra.name == viewer for ra in sample_data.RAS)
    # Staff see RA Leave only while they oversee some RA (author, 2026-10-29).
    is_staff = any(name == viewer for name, _ in sample_leave.STAFF_VIEWERS) and bool(sample_leave.scope(viewer))
    is_sys_admin = any(name == viewer for name, *_ in sample_data.SYS_ADMINS)
    staff_query = "" if viewer == sample_leave.STAFF_VIEWERS[0][0] else f"?as={quote(viewer)}"
    found = []
    if is_ra:
        found.append({"label": "RA Leave", "path": "/ra-leave/", "what": "Your balance, apply for leave, cover asked of you"})
    elif is_staff:
        found.append({"label": "RA Leave", "path": "/ra-leave/staff/" + staff_query, "what": "Decisions awaiting you and your Precinct's leave"})
    found.append({"label": "RA Events", "path": "", "what": "Coming later"})
    if is_sys_admin:
        found += [
            {"label": "RA Leave admin", "path": "/ra-leave/admin/", "what": "Policy, entitlements, approval chain, applications, appeals"},
            {"label": "Rosters and setup", "path": "/rosters/", "what": "Setup, rosters and assignments"},
            {"label": "Sys admin", "path": "/sys-admin/", "what": "Audit log and sys admin grants"},
        ]
    return found


def areas_for(viewer: str) -> tuple[dict[str, str | None], ...]:
    """The switcher for a sample viewer (§2): the landing, then what they
    reach, carrying a staff viewer's `?as=`."""
    landing = "/" if viewer == sample_data.LANDING_VIEWERS[0][0] else f"/?as={quote(viewer)}"
    return (
        {"label": "Home", "path": landing},
        *({"label": c["label"], "path": c["path"] or None} for c in choices(viewer)),
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
    """An RA's tabs; Extra leave only while the RA may send an appeal."""
    return (
        {"label": "Home", "path": "/ra-leave/"},
        {"label": "Apply", "path": "/ra-leave/apply"},
        *(({"label": "Extra leave", "path": "/ra-leave/appeal"},) if appeals else ()),
        {"label": "My cover", "path": "/ra-leave/cover"},
        {"label": "History", "path": "/ra-leave/history"},
    )


def leave_staff_tabs(query: str = "", appeals: bool = False) -> tuple[dict[str, str | None], ...]:
    """A staff member's tabs, the same for every staff member who oversees
    RAs, carrying the sample viewer (`?as=`); Appeals while the Master
    decides appeals."""
    return tuple(
        {"label": label, "path": path, "query": query}
        for label, path in (
            ("Home", "/ra-leave/staff/"),
            ("Awaiting", "/ra-leave/staff/decide"),
            ("Decided", "/ra-leave/staff/decided"),
            ("Precinct leave", "/ra-leave/staff/precinct"),
            *((("Appeals", "/ra-leave/staff/appeals"),) if appeals else ()),
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
