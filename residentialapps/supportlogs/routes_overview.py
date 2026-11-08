"""Support Logs' Overview on sample data, segment 1D item 1 rung 5: senior
staff's and Other Staff view's tab (author, 2026-10-29). Since the
sharing screens' rung 1 (author, 2026-11-07) it shows metadata only: who
supports whom (on Staff Overview since 2026-11-08), students across staff,
every formal plan and the flagged
students (the cluster view, §10.5, is deferred); a senior's view of a
student, the staff with records (§11.2); and the support-activity audit
(§11.3). Aggregate view sees counts only, never a student's name
(roles rule 8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request
from starlette.responses import Response

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.pages import gated
from residentialapps.web.pages import placeholders_previewers_only

router = APIRouter(dependencies=[Depends(placeholders_previewers_only)])

OVERVIEW = (sample.SENIOR, *sample.VIEW)


@router.get("/oversight-students/", name="supportlogs_overview")
def overview(request: Request) -> Response:
    me = sample.viewer(request.query_params.get("as"))
    return gated(
        request,
        "supportlogs/overview.html",
        *OVERVIEW,
        named=sample.holds(me, sample.SENIOR, sample.VIEW_IDENTIFIABLE),
        senior=sample.holds(me, sample.SENIOR),
    )


@router.get("/oversight-staff/", name="supportlogs_workload")
def workload(request: Request) -> Response:
    """Who supports whom on a tab of its own, full width (author,
    2026-11-08), for whoever has Overview: per staff member, students and
    formal plans; for senior staff, the workload for a term."""
    me = sample.viewer(request.query_params.get("as"))
    # The term: the current one by default, "all" for every term; an
    # unknown key reads as the current term.
    key = request.query_params.get("term", sample.CURRENT_TERM.key)
    chosen = None if key == "all" else sample.term(key) or sample.CURRENT_TERM
    return gated(
        request,
        "supportlogs/workload.html",
        *OVERVIEW,
        senior=sample.holds(me, sample.SENIOR),
        chosen_term=chosen,
    )


@router.get("/oversight-students/{sid}", name="supportlogs_overview_student")
def history(request: Request, sid: str) -> Response:
    """A student's history across staff (§4.5, §11.2), for senior
    identifiable access: an audited read."""
    me = sample.viewer(request.query_params.get("as"))
    if not sample.holds(me, sample.SENIOR):
        return gated(request, "supportlogs/history.html", sample.SENIOR)  # the 403 page
    found = sample.student(sid)
    if found is None:
        raise HTTPException(status_code=404)
    return gated(
        request,
        "supportlogs/history.html",
        sample.SENIOR,
        chosen=found,
        current_tab="/oversight-students/",
    )


@router.get("/oversight-staff/audit", name="supportlogs_overview_audit")
def audit(request: Request) -> Response:
    """The support-activity audit (§11.3): who did or saw what, of whom; for
    senior identifiable access only, and reviewing it is recorded."""
    return gated(request, "supportlogs/audit.html", sample.SENIOR, current_tab="/oversight-staff/")


@router.get("/oversight-staff/access", name="supportlogs_overview_access")
def access(request: Request) -> Response:
    """Who holds each Support Logs grant and the access changes, read-only,
    for senior identifiable access (author, 2026-10-30): administration
    decides who sees content, and senior staff see what it decided."""
    return gated(
        request, "supportlogs/overview_access.html", sample.SENIOR, current_tab="/oversight-staff/"
    )
