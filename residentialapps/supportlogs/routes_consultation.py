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
from residentialapps.supportlogs.pages import forbidden, gated, query
from residentialapps.web.pages import placeholders_previewers_only
from residentialapps.web.urls import url_path

router = APIRouter(dependencies=[Depends(placeholders_previewers_only)])


@router.get("/consultation/", name="supportlogs_consultation")
def consultation(request: Request) -> Response:
    """The check's form, keeping what a returned check carried, and the
    viewer's own past runs. `?sample=1` fills the form with the sample
    list."""
    q = request.query_params
    filled = q.get("sample") == "1"
    return gated(request, "supportlogs/consultation.html", sample.CONSULTATION,
                 purpose="Overseas field trip, Semester 2" if filled else q.get("purpose", ""),
                 emails="\n".join(sample.SAMPLE_EMAILS) if filled else q.get("emails", ""),
                 filled=filled)


@router.get("/consultation/check", name="supportlogs_consultation_check")
def check(request: Request) -> Response:
    """A check's result, one row per distinct email, strongest state first,
    and any entry it could not read. A missing purpose or no address goes
    back to the form with what was typed."""
    me = sample.viewer(request.query_params.get("as"))
    if not sample.holds(me, sample.CONSULTATION):
        return forbidden(request, me)
    purpose = request.query_params.get("purpose", "").strip()
    text = request.query_params.get("emails", "")
    emails, unread = sample.emails_in(text)
    if not purpose or not emails:
        return RedirectResponse(url_path(request, "/consultation/") + query(me, purpose=purpose, emails=text.strip()),
                                status_code=303)
    rank = {state: n for n, state in enumerate(sample.CONSULTATION_STATES)}
    results = sorted((sample.consultation(e) for e in emails), key=lambda r: rank[r.state])
    return gated(request, "supportlogs/consultation_check.html", sample.CONSULTATION,
                 purpose=purpose, results=results, unread=unread, current_tab="/consultation/")
