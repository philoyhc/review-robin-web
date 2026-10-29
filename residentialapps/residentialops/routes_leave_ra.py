"""RA Leave's RA pages (`/ra-leave/`): placeholder screens with sample
data for a sample viewer chosen with `?as=` (Chloe Lim by default),
segment 1C item 1, phone first."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request
from starlette.responses import Response

from residentialapps.residentialops import sample_data, sample_leave
from residentialapps.residentialops.pages import areas_for, leave_ra_tabs, placeholders_local_only, render
from residentialapps.web.urls import app_path

router = APIRouter(dependencies=[Depends(placeholders_local_only)])


def _viewer(request: Request) -> str:
    return sample_leave.ra_viewer(request.query_params.get("as"))


def _page(request: Request, template: str, **context: object) -> Response:
    viewer = _viewer(request)
    as_query = "" if viewer == sample_leave.VIEWER else f"?as={quote(viewer)}"
    return render(
        request,
        f"residentialops/leave/ra/{template}",
        area="RA Leave",
        tabs=leave_ra_tabs(sample_leave.can_appeal(viewer), as_query),
        areas=areas_for(viewer),
        leave=sample_leave,
        sample=sample_data,
        me=viewer,
        as_query=as_query,
        here=app_path(request),
        **context,
    )


@router.get("/ra-leave/", name="residentialops_leave_home")
def home(request: Request) -> Response:
    return _page(request, "home.html")


@router.get("/ra-leave/apply", name="residentialops_leave_apply")
def apply(request: Request) -> Response:
    # A saved draft reopens here, filled in (author, 2026-10-29); only the
    # RA's own.
    key = request.query_params.get("draft")
    draft = next((d for d in sample_leave.my_drafts(_viewer(request)) if d.id == key), None)
    if key and draft is None:
        raise HTTPException(status_code=404)
    return _page(request, "apply.html", draft=draft)


@router.get("/ra-leave/appeal", name="residentialops_leave_appeal")
def appeal(request: Request) -> Response:
    # By invitation the appeal is not shown to an RA until they are invited
    # (author, 2026-10-29): uninvited, the page does not exist for them.
    if sample_leave.POLICY["appeals"] == "By invitation" and not sample_leave.can_appeal(_viewer(request)):
        raise HTTPException(status_code=404)
    return _page(request, "appeal.html")


@router.get("/ra-leave/applications/{application_id}", name="residentialops_leave_application")
def application(request: Request, application_id: str) -> Response:
    # An RA sees only their own applications.
    found = sample_leave.by_id(application_id)
    if found is None or found.ra != _viewer(request):
        raise HTTPException(status_code=404)
    return _page(request, "application.html", app=found, steps=sample_leave.timeline(found), current_tab="/ra-leave/history")


@router.get("/ra-leave/cover", name="residentialops_leave_cover")
def cover(request: Request) -> Response:
    return _page(request, "cover.html", asked=sample_leave.cover_asked(_viewer(request)))


@router.get("/ra-leave/history", name="residentialops_leave_history")
def history(request: Request) -> Response:
    return _page(request, "history.html")
