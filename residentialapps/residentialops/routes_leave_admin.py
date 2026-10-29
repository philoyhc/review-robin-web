"""RA Leave's sys admin pages (`/ra-leave/admin/`): placeholder screens with
sample data, segment 1C item 1. Built first, the rest of RA Leave being
downstream of its configuration (author, 2026-10-28)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request
from starlette.responses import Response

from residentialapps.residentialops import sample_data, sample_leave
from residentialapps.residentialops.pages import LEAVE_ADMIN_TABS, placeholders_local_only, render

router = APIRouter(dependencies=[Depends(placeholders_local_only)])


def _page(request: Request, template: str, **context: object) -> Response:
    return render(
        request,
        f"residentialops/leave/admin/{template}",
        area="RA Leave",
        tabs=LEAVE_ADMIN_TABS,
        leave=sample_leave,
        sample=sample_data,
        **context,
    )


@router.get("/ra-leave/admin/", name="residentialops_leave_admin")
def dashboard(request: Request) -> Response:
    return _page(request, "dashboard.html")


@router.get("/ra-leave/admin/policy", name="residentialops_leave_admin_policy")
def policy(request: Request) -> Response:
    return _page(request, "policy.html")


@router.get("/ra-leave/admin/entitlements", name="residentialops_leave_admin_entitlements")
def entitlements(request: Request) -> Response:
    return _page(request, "entitlements.html", rows=sample_leave.entitlement_rows())


@router.get("/ra-leave/admin/routing", name="residentialops_leave_admin_routing")
def routing(request: Request) -> Response:
    staff = [p.name for p in sample_data.STAFF]
    return _page(request, "routing.html", routes=sample_leave.routes(), staff=staff, delegable=sample_leave.delegable())


@router.get("/ra-leave/admin/appeals", name="residentialops_leave_admin_appeals")
def appeals(request: Request) -> Response:
    ras = tuple(p.name for p in sample_data.RAS)
    return _page(request, "appeals.html", ra_choices=ras, agreers=sample_leave.all_inviters())


@router.get("/ra-leave/admin/applications", name="residentialops_leave_admin_applications")
def applications(request: Request) -> Response:
    # The dashboard's tiles link here filtered (`?stage=`, `?cover=`); the
    # rest of the filter card is inert until item 2.
    stage = request.query_params.get("stage", "")
    cover = request.query_params.get("cover", "")
    shown = tuple(
        a for a in sample_leave.APPLICATIONS
        if (not stage or a.stage == stage) and (cover != "unconfirmed" or a in sample_leave.cover_unconfirmed())
    )
    return _page(request, "applications.html", shown=shown, stage=stage, cover=cover)


@router.get("/ra-leave/admin/applications/{application_id}", name="residentialops_leave_admin_application")
def application(request: Request, application_id: str) -> Response:
    found = sample_leave.by_id(application_id)
    if found is None:
        raise HTTPException(status_code=404)
    return _page(
        request, "application.html", app=found, steps=sample_leave.timeline(found),
        current_tab="/ra-leave/admin/applications",
    )
