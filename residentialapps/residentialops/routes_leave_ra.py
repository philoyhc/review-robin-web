"""RA Leave's RA pages (`/ra-leave/`): placeholder screens with sample
data for a sample viewer chosen with `?as=` (Chloe Lim by default),
segment 1C item 1, phone first."""

from __future__ import annotations

from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from residentialapps.residentialops import sample_data, sample_leave
from residentialapps.residentialops.pages import (
    areas_for,
    leave_ra_tabs,
    ra_pages_previewers,
    render,
)
from residentialapps.web.urls import app_path

# Previewers, and RA previewers too (author, 2026-11-09).
router = APIRouter(dependencies=[Depends(ra_pages_previewers)])


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


def _day(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


@router.get("/ra-leave/check-dates", name="residentialops_leave_check_dates")
def check_dates(request: Request) -> Response:
    """Apply's and Request extra leave's live check of the dates keyed in
    (author, 2026-11-09): the days they count, what is wrong, and whether
    the form may be sent."""
    q = request.query_params
    viewer = _viewer(request)
    leave_type = q.get("type") or sample_leave.LEAVE_TYPES[0].name
    # Appeal rules only for an RA who may appeal now, as the appeal page.
    appeal = q.get("appeal") == "1" and sample_leave.can_appeal(viewer)
    first, last = _day(q.get("first")), _day(q.get("last"))
    result: dict[str, object] = dict(
        sample_leave.check_dates(
            viewer, leave_type, first, last, appeal=appeal, cover=q.get("cover") or ""
        )
    )
    # Whom the cover list may not offer for these dates (author, 2026-11-10).
    result["unavailable"] = (
        list(sample_leave.away_between_names(first, last))
        if first and last and first <= last
        else []
    )
    return JSONResponse(result)


@router.get("/ra-leave/appeal", name="residentialops_leave_appeal")
def appeal(request: Request) -> Response:
    # The page exists only for an RA who may appeal now: never while appeals
    # are Off, and by invitation, the default (author, 2026-11-09), only once
    # invited (author, 2026-10-29).
    if not sample_leave.can_appeal(_viewer(request)):
        raise HTTPException(status_code=404)
    return _page(request, "appeal.html")


@router.get("/ra-leave/applications/{application_id}", name="residentialops_leave_application")
def application(request: Request, application_id: str) -> Response:
    # An RA sees only their own applications.
    found = sample_leave.by_id(application_id)
    if found is None or found.ra != _viewer(request):
        raise HTTPException(status_code=404)
    return _page(
        request,
        "application.html",
        app=found,
        steps=sample_leave.timeline(found),
        current_tab="/ra-leave/history",
    )


@router.get("/ra-leave/cover", name="residentialops_leave_cover")
def cover(request: Request) -> Response:
    return _page(request, "cover.html", asked=sample_leave.cover_asked(_viewer(request)))


@router.get("/ra-leave/history", name="residentialops_leave_history")
def history(request: Request) -> Response:
    return _page(request, "history.html")
