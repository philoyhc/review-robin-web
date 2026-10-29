"""RA Leave's staff pages (`/ra-leave/staff/`): placeholder screens with
sample data for a sample viewer chosen on the banner (`?as=`), segment 1C
item 1. Deciding is mobile-critical; Precinct leave is desktop-oriented."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request
from starlette.responses import Response

from residentialapps.residentialops import sample_data, sample_leave
from residentialapps.residentialops.pages import areas_for, leave_staff_tabs, placeholders_local_only, render
from residentialapps.web.urls import app_path

router = APIRouter(dependencies=[Depends(placeholders_local_only)])


def _page(request: Request, template: str, **context: object) -> Response:
    viewer = sample_leave.staff_viewer(request.query_params.get("as"))
    as_query = "" if viewer == sample_leave.STAFF_VIEWERS[0][0] else f"?as={quote(viewer)}"
    return render(
        request,
        f"residentialops/leave/staff/{template}",
        area="RA Leave",
        tabs=leave_staff_tabs(as_query, appeals=bool(sample_leave.invitable_ras(viewer))),
        areas=areas_for(viewer),
        leave=sample_leave,
        sample=sample_data,
        me=viewer,
        as_query=as_query,
        here=app_path(request),
        **context,
    )


@router.get("/ra-leave/staff/", name="residentialops_leave_staff")
def home(request: Request) -> Response:
    return _page(request, "home.html")


@router.get("/ra-leave/staff/decide", name="residentialops_leave_staff_queue")
def awaiting(request: Request) -> Response:
    # Staff home's "waiting on cover" tile opens the queue filtered.
    return _page(request, "queue.html", cover_only=request.query_params.get("cover") == "waiting")


@router.get("/ra-leave/staff/decide/{application_id}", name="residentialops_leave_staff_decide")
def decide(request: Request, application_id: str) -> Response:
    # A staff member opens an application in their own scope only; it is
    # actionable when it awaits their decision, read-only otherwise.
    viewer = sample_leave.staff_viewer(request.query_params.get("as"))
    found = sample_leave.by_id(application_id)
    if found is None or not sample_leave.can_open(viewer, found):
        raise HTTPException(status_code=404)
    role = next((r for a, r in sample_leave.queue(viewer) if a.id == found.id), None)
    # Back to the list it was most likely opened from, which its tab marks.
    if role:
        back = ("/ra-leave/staff/decide", "Awaiting my decision")
    elif any(a.id == found.id for a, _, _ in sample_leave.decided(viewer)):
        back = ("/ra-leave/staff/decided", "Decided")
    elif found.precinct in sample_leave.scope(viewer):
        back = ("/ra-leave/staff/precinct", "Precinct leave")
    else:
        back = ("/ra-leave/staff/appeals", "Appeals")
    return _page(
        request, "decide.html", app=found, role=role, steps=sample_leave.timeline(found),
        back_path=back[0], back_label=back[1], current_tab=back[0],
    )


@router.get("/ra-leave/staff/decided", name="residentialops_leave_staff_decided")
def decided(request: Request) -> Response:
    return _page(request, "decided.html")


@router.get("/ra-leave/staff/precinct", name="residentialops_leave_staff_precinct")
def precinct(request: Request) -> Response:
    return _page(request, "precinct.html")


@router.get("/ra-leave/staff/appeals", name="residentialops_leave_staff_appeals")
def appeals(request: Request) -> Response:
    # Whoever the policy lets open appeals does so here as on the admin
    # page (author, 2026-10-29), for the RAs they may; others are told.
    viewer = sample_leave.staff_viewer(request.query_params.get("as"))
    ras = sample_leave.invitable_ras(viewer)
    return _page(request, "appeals.html", allowed=bool(ras), ra_choices=ras, agreers=(viewer,))
