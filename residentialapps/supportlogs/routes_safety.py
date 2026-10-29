"""Support Logs' safety pages on sample data, segment 1D item 1 rung 3: the
Safety concern form and its confirmation, and a safety flag's detail (UI
spec screens 4 and 8; functional spec §5.10). The flags' lists are on Home
and Overview, not a tab of their own (author, 2026-10-29). Nothing is
stored: raising shows the confirmation, and a recipient's actions wait on
item 3."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.pages import flags_tab, gated, query
from residentialapps.web.pages import placeholders_local_only
from residentialapps.web.urls import url_path

router = APIRouter(dependencies=[Depends(placeholders_local_only)])


def _context(request: Request) -> dict:
    """The encounter context carried from Log encounter: whichever of the
    student, duration and type were chosen, valid ones only."""
    q = request.query_params
    chosen = sample.student(q.get("student"))
    return {
        "chosen": chosen,
        "duration": q.get("duration") if q.get("duration") in sample.DURATIONS else None,
        "kind": q.get("type") if q.get("type") in sample.ENCOUNTER_TYPES else None,
    }


@router.get("/log/safety", name="supportlogs_log_safety")
def safety(request: Request) -> Response:
    """Safety concern (UI spec screen 4): the call actions first, then the
    encounter's context, the crisis protocol and the escalation step."""
    return gated(request, "supportlogs/safety.html", sample.FRONTLINE, current_tab="/log", **_context(request))


@router.get("/log/safety/raised", name="supportlogs_log_safety_raised")
def safety_raised(request: Request) -> Response:
    """The confirmation once a flag is raised. A sample: nothing is stored.
    Anything missing goes back to the form with what was chosen."""
    me = sample.viewer(request.query_params.get("as"))
    if not sample.holds(me, sample.FRONTLINE):
        return gated(request, "supportlogs/safety_raised.html", sample.FRONTLINE)  # the 403 page
    context = _context(request)
    step = request.query_params.get("step")
    if not (context["chosen"] and context["duration"] and context["kind"] and step in sample.ESCALATION_STEPS):
        kept = {"student": context["chosen"].id if context["chosen"] else "",
                "duration": context["duration"] or "", "type": context["kind"] or ""}
        return RedirectResponse(url_path(request, "/log/safety") + query(me, **kept), status_code=303)
    in_set = any(s.id == context["chosen"].id for s, _, _ in sample.working_set(me.name))
    at = request.query_params.get("at", "")
    at = at.replace("T", " ") if len(at) == 16 and at[10] == "T" else ""  # a datetime-local value, shown as given
    return gated(request, "supportlogs/safety_raised.html", sample.FRONTLINE, current_tab="/log",
                 step=step, at=at, in_set=in_set, **context)


@router.get("/flags/{fid}", name="supportlogs_flag")
def flag_detail(request: Request, fid: str) -> Response:
    """A safety flag (UI spec screen 8): its student, who raised it, the
    step recorded and its state; a recipient acknowledges it and closes it
    with an outcome, its raiser sees state and outcome only. A flag the
    viewer may not see is not found."""
    me = sample.viewer(request.query_params.get("as"))
    if not sample.holds(me, sample.FRONTLINE, sample.RECIPIENT):
        return gated(request, "supportlogs/flag.html", sample.FRONTLINE, sample.RECIPIENT)  # the 403 page
    found = sample.flag(fid)
    if found is None or not sample.may_see(me, found):
        raise HTTPException(status_code=404)
    back = flags_tab(me) or "/"
    in_set = any(s.id == found.student for s, _, _ in sample.working_set(me.name))
    return gated(request, "supportlogs/flag.html", sample.FRONTLINE, sample.RECIPIENT,
                 f=found, back=back, in_set=in_set, current_tab=back)
