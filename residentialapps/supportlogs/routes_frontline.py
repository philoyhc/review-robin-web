"""Support Logs' frontline pages on sample data, segment 1D item 1 rung 2:
Log encounter with its optional details and the confirmation after
saving, Students and the student view, and My plans (UI spec screens
2–3, 5–7; functional spec §4–§7, §9). The dashboard is Home
(`routes_home.py`). Nothing is stored: Save shows the confirmation for
the choices made, and the student view's actions wait on their rungs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.pages import gated, reaches_student, records_unlocked
from residentialapps.web.pages import placeholders_previewers_only
from residentialapps.web.urls import url_path

router = APIRouter(dependencies=[Depends(placeholders_previewers_only)])

FRONTLINE = sample.FRONTLINE


def _me(request: Request) -> sample.Viewer:
    return sample.viewer(request.query_params.get("as"))


@router.get("/log", name="supportlogs_log")
def log(request: Request) -> Response:
    # Opened from a student or a Log button, the student is chosen already.
    # Back from Safety concern keeps the duration and type chosen too.
    q = request.query_params
    chosen = sample.student(q.get("student"))
    duration = q.get("duration") if q.get("duration") in sample.DURATIONS else None
    kind = q.get("type") if q.get("type") in sample.ENCOUNTER_TYPES else None
    return gated(request, "supportlogs/log.html", FRONTLINE, chosen=chosen, duration=duration, kind=kind, current_tab="/log")


@router.get("/log/saved", name="supportlogs_log_saved")
def log_saved(request: Request) -> Response:
    """The confirmation after Save (UI spec §3, "After saving"): what was
    saved and, for a student not on the viewer's plans, Add to my
    follow-ups. A sample: nothing is stored."""
    q = request.query_params
    me = _me(request)
    chosen = sample.student(q.get("student"))
    duration, kind = q.get("duration"), q.get("type")
    if chosen is None or duration not in sample.DURATIONS or kind not in sample.ENCOUNTER_TYPES:
        return RedirectResponse(url_path(request, "/log") + sample.as_query(me), status_code=303)
    following = bool(sample.plans_of(me.name, chosen.id))
    # The saved encounter makes the student one of the viewer's own (§4.3);
    # a sample stores nothing, so the view is offered only if already so.
    in_set = any(s.id == chosen.id for s, _, _ in sample.working_set(me.name))
    return gated(
        request, "supportlogs/log_saved.html", FRONTLINE,
        chosen=chosen, duration=duration, kind=kind, following=following, in_set=in_set,
        added=q.get("follow") == "yes" and not following, current_tab="/log",
    )


@router.get("/students/", name="supportlogs_students")
def students(request: Request) -> Response:
    return gated(request, "supportlogs/students.html", FRONTLINE, unlocked=records_unlocked(request))


@router.get("/students/{sid}", name="supportlogs_student")
def student_view(request: Request, sid: str) -> Response:
    """The student view (§9; UI spec screen 5). A student outside the
    viewer's own working set, and not shared with them by a colleague, is
    not found, as RA Leave's other RAs' applications are: the view shows
    only what the viewer's records and grants cover (§11.1)."""
    me = _me(request)
    if not sample.holds(me, FRONTLINE):
        return gated(request, "supportlogs/student.html", FRONTLINE)  # the 403 page, whatever the id
    found = sample.student(sid)
    if found is None or not reaches_student(me, sid):
        raise HTTPException(status_code=404)
    return gated(request, "supportlogs/student.html", FRONTLINE, chosen=found, current_tab="/students/")


SHOW = {"all": "All", "overdue": "Overdue", "week": "This week"}


@router.get("/plans/", name="supportlogs_plans")
def plans(request: Request) -> Response:
    """My plans (UI spec screen 6): formal assignments, then informal
    follow-ups, filtered All, Overdue or This week."""
    show = request.query_params.get("show", "all")
    show = show if show in SHOW else "all"
    keep = {"all": None, "overdue": {"overdue"}, "week": {"overdue", "today", "week"}}[show]
    me = _me(request)
    mine = [p for p in sample.plans_of(me.name) if keep is None or sample.due(p)[0] in keep]
    return gated(request, "supportlogs/plans.html", FRONTLINE, show=show, shows=SHOW, mine=mine,
                 unlocked=records_unlocked(request))
