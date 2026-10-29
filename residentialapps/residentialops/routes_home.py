"""Residential Operations' landing (`/`): choose an application the
viewer reaches (author, 2026-10-28). A placeholder on sample data, drawn
for a sample viewer chosen on the page (`?as=`), segment 1C item 1."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import Response

from residentialapps.residentialops import sample_data, sample_leave
from residentialapps.residentialops.pages import placeholders_local_only, render

router = APIRouter(dependencies=[Depends(placeholders_local_only)])


def choices(viewer: str) -> list[dict[str, str]]:
    """The applications the viewer reaches, each at its own entry point:
    RA Leave's RA, staff or admin side by who they are; Rosters and Sys
    admin for sys admins only."""
    is_ra = any(ra.name == viewer for ra in sample_data.RAS)
    is_staff = any(name == viewer for name, _ in sample_leave.STAFF_VIEWERS)
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
            {"label": "Rosters", "path": "/rosters/", "what": "Setup, rosters and assignments"},
            {"label": "Sys admin", "path": "/sys-admin/", "what": "Audit log and sys admin grants"},
        ]
    return found


@router.get("/", name="residentialops_home")
def home(request: Request) -> Response:
    names = [n for n, _ in sample_data.LANDING_VIEWERS]
    viewer = request.query_params.get("as")
    viewer = viewer if viewer in names else names[0]
    return render(
        request,
        "residentialops/home.html",
        area="Home",
        sample=sample_data,
        me=viewer,
        role=dict(sample_data.LANDING_VIEWERS)[viewer],
        apps=choices(viewer),
    )
