"""Residential Operations' page rendering: its templates and the chrome's
context (`residentialapps/spec/residentialops_ui.md` §2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from starlette.requests import Request
from starlette.responses import Response

from cordware.identity import current_identity
from residentialapps.residentialops import sample_data, sample_leave
from residentialapps.web.pages import initials
from residentialapps.web.pages import placeholders_local_only as placeholders_local_only  # for the routes
from residentialapps.web.urls import templates

TEMPLATES = templates([Path(__file__).resolve().parent / "templates"])

APP_NAME = "Residential Operations"


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
        ra_query = "" if viewer == sample_leave.VIEWER else f"?as={quote(viewer)}"
        found.append({"label": "RA Leave", "path": "/ra-leave/" + ra_query, "what": "Your balance, apply for leave, cover asked of you"})
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
    # The landing knows its own viewers; anyone else goes to its default.
    known = viewer in dict(sample_data.LANDING_VIEWERS) and viewer != sample_data.LANDING_VIEWERS[0][0]
    landing = f"/?as={quote(viewer)}" if known else "/"
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

def leave_ra_tabs(appeals: bool, query: str = "") -> tuple[dict[str, str | None], ...]:
    """An RA's tabs, carrying the sample viewer (`?as=`); Extra leave only
    while the RA may send an appeal."""
    return tuple(
        {"label": label, "path": path, "query": query}
        for label, path in (
            ("Home", "/ra-leave/"),
            ("Apply", "/ra-leave/apply"),
            *((("Extra leave", "/ra-leave/appeal"),) if appeals else ()),
            ("My cover", "/ra-leave/cover"),
            ("History", "/ra-leave/history"),
        )
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


async def sample_preview(request: Request) -> None:
    """The appeal mode this browser previews (`Leave policy`'s sample
    switch, audit 2026-10-29), set for the request before any page reads the
    policy. Async, so the value carries into the threadpool the page runs in."""
    mode = request.cookies.get(sample_leave.PREVIEW_COOKIE)
    if mode in sample_leave.APPEAL_MODES:
        sample_leave.APPEALS_PREVIEW.set(mode)


def render(
    request: Request,
    template: str,
    *,
    area: str,
    tabs: tuple[dict[str, str | None], ...] = (),
    areas: tuple[dict[str, str | None], ...] | None = None,
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
            # A sys admin's pages default to the sample Leave admin's switcher
            # (§2), as RA Leave admin's do; a path of None is an area not
            # built yet.
            "areas": areas_for(sample_leave.CANCELLED_BY) if areas is None else areas,
            "tabs": tabs,
            "viewer": viewer,
            "initials": initials(viewer.display_label) if viewer else "?",
            **context,
        },
    )
