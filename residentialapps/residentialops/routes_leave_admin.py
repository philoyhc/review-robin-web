"""RA Leave's sys admin pages (`/ra-leave/admin/`): placeholder screens with
sample data, segment 1C item 1. Built first, the rest of RA Leave being
downstream of its configuration (author, 2026-10-28)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from residentialapps.residentialops import sample_data, sample_leave
from residentialapps.residentialops.pages import (
    LEAVE_ADMIN_TABS,
    placeholders_previewers_only,
    render,
)
from residentialapps.web.urls import app_path, url_path

router = APIRouter(dependencies=[Depends(placeholders_previewers_only)])


def _page(request: Request, template: str, **context: Any) -> Response:
    return render(
        request,
        f"residentialops/leave/admin/{template}",
        area="RA Leave admin",
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


@router.get(
    "/ra-leave/admin/policy/preview-appeals", name="residentialops_leave_admin_preview_appeals"
)
def preview_appeals(request: Request) -> Response:
    # Sample-only (audit, 2026-10-29): preview every RA Leave page as if
    # appeals were in a mode, in this browser; the policy's own mode clears it.
    mode = request.query_params.get("mode", "")
    response = RedirectResponse(
        url_path(request, "/ra-leave/admin/policy") + "#appeals-h", status_code=303
    )
    if mode in sample_leave.APPEAL_MODES and mode != sample_leave.policy_appeals():
        response.set_cookie(
            sample_leave.PREVIEW_COOKIE,
            mode,
            path=url_path(request, "/"),
            samesite="lax",
            httponly=True,
        )
    else:
        response.delete_cookie(sample_leave.PREVIEW_COOKIE, path=url_path(request, "/"))
    return response


@router.get("/ra-leave/admin/entitlements", name="residentialops_leave_admin_entitlements")
def entitlements(request: Request) -> Response:
    return _page(request, "entitlements.html", rows=sample_leave.entitlement_rows())


@router.get("/ra-leave/admin/routing", name="residentialops_leave_admin_routing")
def routing(request: Request) -> Response:
    return _page(
        request, "routing.html", routes=sample_leave.routes(), delegable=sample_leave.delegable()
    )


@router.get("/ra-leave/admin/appeals", name="residentialops_leave_admin_appeals")
def appeals(request: Request) -> Response:
    ras = tuple(p.name for p in sample_data.RAS)
    # The form opens appeals only by invitation; open or off, the card says
    # why there is none to open, as on the staff page.
    may_open = sample_leave.POLICY["appeals"] == "By invitation" and bool(
        sample_leave.all_inviters()
    )
    return _page(
        request,
        "appeals.html",
        may_open=may_open,
        ra_choices=ras,
        agreers=sample_leave.all_inviters(),
    )


@router.get("/ra-leave/admin/records", name="residentialops_leave_admin_records")
def records(request: Request) -> Response:
    # Leave records (author, 2026-11-10; Applications until then): the
    # staff's Records card over the whole Unit, its filters the same chips
    # and period, Export and Record external leave under the table.
    q = request.query_params
    return _page(
        request,
        "records.html",
        # The whole term by default: the admin keeps the record (the cold
        # read, 2026-11-10; Applications listed every application).
        period=sample_leave.period_range(q.get("period"), q.get("from"), q.get("to"), "whole"),
        hide=q.get("hide"),
        here=app_path(request),
    )


@router.get("/ra-leave/admin/applications", name="residentialops_leave_admin_applications")
def applications(request: Request) -> Response:
    # Applications became Leave records (author, 2026-11-10); an old link,
    # the dashboard's filtered ones too, lands there, its query kept.
    return _moved(request, "/ra-leave/admin/records")


@router.get(
    "/ra-leave/admin/applications/{application_id}",
    name="residentialops_leave_admin_application_old",
)
def application_old(request: Request, application_id: str) -> Response:
    return _moved(request, f"/ra-leave/admin/records/{application_id}")


def _moved(request: Request, path: str) -> Response:
    query = request.url.query
    return RedirectResponse(
        url_path(request, path) + (f"?{query}" if query else ""), status_code=303
    )


@router.get(
    "/ra-leave/admin/records/{application_id}", name="residentialops_leave_admin_application"
)
def application(request: Request, application_id: str) -> Response:
    found = sample_leave.by_id(application_id)
    if found is None:
        raise HTTPException(status_code=404)
    return _page(
        request,
        "application.html",
        app=found,
        steps=sample_leave.timeline(found),
        current_tab="/ra-leave/admin/records",
    )
