"""RA Leave's RA pages (`/ra-leave/`): placeholder screens with sample
data for one sample viewer, segment 1C item 1, phone first."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request
from starlette.responses import Response

from residentialapps.residentialops import sample_data, sample_leave
from residentialapps.residentialops.pages import leave_ra_tabs, placeholders_local_only, render

router = APIRouter(dependencies=[Depends(placeholders_local_only)])


def _page(request: Request, template: str, **context: object) -> Response:
    return render(
        request,
        f"residentialops/leave/ra/{template}",
        area="RA Leave",
        tabs=leave_ra_tabs(bool(sample_leave.POLICY["appeals"])),
        leave=sample_leave,
        sample=sample_data,
        me=sample_leave.VIEWER,
        **context,
    )


@router.get("/ra-leave/", name="residentialops_leave_home")
def home(request: Request) -> Response:
    return _page(request, "home.html")


@router.get("/ra-leave/apply", name="residentialops_leave_apply")
def apply(request: Request) -> Response:
    return _page(request, "apply.html")


@router.get("/ra-leave/appeal", name="residentialops_leave_appeal")
def appeal(request: Request) -> Response:
    return _page(request, "appeal.html")


@router.get("/ra-leave/applications/{application_id}", name="residentialops_leave_application")
def application(request: Request, application_id: str) -> Response:
    # An RA sees only their own applications.
    found = sample_leave.by_id(application_id)
    if found is None or found.ra != sample_leave.VIEWER:
        raise HTTPException(status_code=404)
    return _page(request, "application.html", app=found, steps=sample_leave.timeline(found))


@router.get("/ra-leave/cover", name="residentialops_leave_cover")
def cover(request: Request) -> Response:
    return _page(request, "cover.html", asked=sample_leave.cover_asked())


@router.get("/ra-leave/history", name="residentialops_leave_history")
def history(request: Request) -> Response:
    return _page(request, "history.html")
