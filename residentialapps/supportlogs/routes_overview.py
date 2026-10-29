"""Support Logs' Overview on sample data, segment 1D item 1 rung 5: senior
staff's and Other Staff view's tab (author, 2026-10-29), with team
workload and load weighting, coverage, hotspots, clusters, every plan and
the flagged students (§10.2–10.6); a senior's student history (§11.2) and
the support-activity audit (§11.3). Aggregate view sees counts only, never
a student's name (roles rule 8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request
from starlette.responses import Response

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.pages import gated
from residentialapps.web.pages import placeholders_local_only

router = APIRouter(dependencies=[Depends(placeholders_local_only)])

OVERVIEW = (sample.SENIOR, *sample.VIEW)


@router.get("/overview/", name="supportlogs_overview")
def overview(request: Request) -> Response:
    me = sample.viewer(request.query_params.get("as"))
    return gated(
        request, "supportlogs/overview.html", *OVERVIEW,
        named=sample.holds(me, sample.SENIOR, sample.VIEW_IDENTIFIABLE),
        senior=sample.holds(me, sample.SENIOR),
    )


@router.get("/overview/students/{sid}", name="supportlogs_overview_student")
def history(request: Request, sid: str) -> Response:
    """A student's history across staff (§4.5, §11.2), for senior
    identifiable access: an audited read."""
    me = sample.viewer(request.query_params.get("as"))
    if not sample.holds(me, sample.SENIOR):
        return gated(request, "supportlogs/history.html", sample.SENIOR)  # the 403 page
    found = sample.student(sid)
    if found is None:
        raise HTTPException(status_code=404)
    return gated(request, "supportlogs/history.html", sample.SENIOR, chosen=found, current_tab="/overview/")


@router.get("/overview/audit", name="supportlogs_overview_audit")
def audit(request: Request) -> Response:
    """The support-activity audit (§11.3): who did or saw what, of whom; for
    senior identifiable access only, and reviewing it is recorded."""
    return gated(request, "supportlogs/audit.html", sample.SENIOR, current_tab="/overview/")
