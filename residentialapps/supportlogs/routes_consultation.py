"""Support Logs' Consultation check on sample data, segment 1D item 1 rung
6: a purpose and a list of students' emails in, each student's state, its
named reasons and whom to consult out (functional spec §10.7–10.8; author,
2026-10-29, "Consultation check"). It never decides a student's
suitability. Nothing is stored: a check shows its result, and the run's
record waits on item 5."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.pages import gated, query
from residentialapps.web.pages import placeholders_local_only
from residentialapps.web.urls import url_path

router = APIRouter(dependencies=[Depends(placeholders_local_only)])


@router.get("/consultation/", name="supportlogs_consultation")
def consultation(request: Request) -> Response:
    """The check's form and past runs. `?sample=1` fills the form with the
    sample list."""
    return gated(request, "supportlogs/consultation.html", sample.CONSULTATION,
                 filled=request.query_params.get("sample") == "1")


@router.get("/consultation/check", name="supportlogs_consultation_check")
def check(request: Request) -> Response:
    """A check's result, one row per distinct email, strongest state first.
    A missing purpose or list goes back to the form."""
    me = sample.viewer(request.query_params.get("as"))
    if not sample.holds(me, sample.CONSULTATION):
        return gated(request, "supportlogs/consultation_check.html", sample.CONSULTATION)  # the 403 page
    purpose = request.query_params.get("purpose", "").strip()
    emails = sample.emails_in(request.query_params.get("emails", ""))
    if not purpose or not emails:
        return RedirectResponse(url_path(request, "/consultation/") + query(me), status_code=303)
    rank = {state: n for n, state in enumerate(sample.CONSULTATION_STATES)}
    results = sorted((sample.consultation(e) for e in emails), key=lambda r: rank[r.state])
    return gated(request, "supportlogs/consultation_check.html", sample.CONSULTATION,
                 purpose=purpose, results=results, current_tab="/consultation/")
