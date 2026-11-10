"""RA Leave's staff pages (`/ra-leave/staff/`): placeholder screens with
sample data for a sample viewer chosen on the banner (`?as=`), segment 1C
item 1. Deciding is mobile-critical; Precinct is desktop-oriented."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from residentialapps.residentialops import sample_data, sample_leave
from residentialapps.residentialops.pages import (
    areas_for,
    leave_staff_tabs,
    placeholders_previewers_only,
    render,
)
from residentialapps.web.urls import app_path, url_path

router = APIRouter(dependencies=[Depends(placeholders_previewers_only)])


def _page(request: Request, template: str, **context: object) -> Response:
    viewer = sample_leave.staff_viewer(request.query_params.get("as"))
    as_query = "" if viewer == sample_leave.STAFF_VIEWERS[0][0] else f"?as={quote(viewer)}"
    # The same pages for every staff member who oversees RAs; one who
    # oversees none is told so, and sees no leave (author, 2026-10-29).
    oversees = bool(sample_leave.scope(viewer))
    if not oversees:
        template, context = "none.html", {}
    return render(
        request,
        f"residentialops/leave/staff/{template}",
        area="RA Leave",
        tabs=leave_staff_tabs(as_query, appeals=sample_leave.sees_appeals(viewer))
        if oversees
        else (),
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
    # Home is also the queue (author, 2026-11-09), filtered to applications
    # waiting on cover by `?cover=waiting`.
    q = request.query_params
    return _page(
        request,
        "home.html",
        cover_only=q.get("cover") == "waiting",
        month=sample_leave.month_of(q.get("month")),
        # The calendar's filters turned off (author, 2026-11-10), e.g.
        # `?hide=Pending,Maple`; the template checks them against the viewer.
        hide=q.get("hide"),
    )


@router.get("/ra-leave/staff/decide", name="residentialops_leave_staff_queue")
def awaiting(request: Request) -> Response:
    # The Awaiting page folded into Home (author, 2026-11-09); an old link
    # lands there, its query (`?as=`, `?cover=`) kept.
    query = request.url.query
    return RedirectResponse(
        url_path(request, "/ra-leave/staff/") + (f"?{query}" if query else ""), status_code=303
    )


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
        back = ("/ra-leave/staff/", "Home")
    elif any(a.id == found.id for a, _, _ in sample_leave.decided(viewer)):
        back = ("/ra-leave/staff/decided", "Decided")
    elif sample_leave.sees_appeals(viewer) and (
        found.appeal or found.ra in sample_leave.invitable_ras(viewer)
    ):
        back = ("/ra-leave/staff/appeals", "Appeals")
    else:
        back = ("/ra-leave/staff/", "Home")
    return _page(
        request,
        "decide.html",
        app=found,
        role=role,
        steps=sample_leave.timeline(found),
        back_path=back[0],
        back_label=back[1],
        current_tab=back[0],
    )


@router.get("/ra-leave/staff/decided", name="residentialops_leave_staff_decided")
def decided(request: Request) -> Response:
    return _page(request, "decided.html")


@router.get("/ra-leave/staff/records", name="residentialops_leave_staff_records")
def records(request: Request) -> Response:
    # Every application in the viewer's scope for a chosen period (spec
    # §22; author, 2026-11-10), this week by default, filtered by status
    # and, for more than one Precinct, by Precinct (`?hide=`).
    q = request.query_params
    return _page(
        request,
        "records.html",
        period=sample_leave.period(q.get("period")),
        hide=q.get("hide"),
        # The Summary's counts turned off (author, 2026-11-10).
        uncount=q.get("uncount"),
    )


@router.get("/ra-leave/staff/precinct", name="residentialops_leave_staff_precinct")
def precinct(request: Request) -> Response:
    # The Precinct page became Leave records (author, 2026-11-10); an old
    # link lands there, its query kept.
    query = request.url.query
    return RedirectResponse(
        url_path(request, "/ra-leave/staff/records") + (f"?{query}" if query else ""),
        status_code=303,
    )


@router.get("/ra-leave/staff/appeals", name="residentialops_leave_staff_appeals")
def appeals(request: Request) -> Response:
    # Every overseer sees the appeals and invitations of their own RAs;
    # whoever the policy lets open appeals does so here, for the RAs they
    # may (author, 2026-10-29).
    viewer = sample_leave.staff_viewer(request.query_params.get("as"))
    ras = sample_leave.invitable_ras(viewer)
    seen = tuple(dict.fromkeys((*sample_leave.ras_in_scope(viewer), *ras)))
    may_open = bool(ras) and sample_leave.POLICY["appeals"] == "By invitation"
    return _page(
        request,
        "appeals.html",
        may_open=may_open,
        ra_choices=ras,
        seen=seen,
        agreers=(viewer,) if may_open else (),
    )
