"""Support Logs' plans and sharing on sample data, segment 1D item 1 rung 4:
a plan's detail with its history and, for senior staff, conversion of a
follow-up to a formal assignment (§7, §8); Flag for formal assignment
(§3.1); and peer-view grants, Share with a colleague (§11.1). Nothing is
stored: each form shows its confirmation, and changes wait on item 4."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.pages import gated, query, reaches_student
from residentialapps.web.pages import placeholders_previewers_only
from residentialapps.web.urls import url_path

router = APIRouter(dependencies=[Depends(placeholders_previewers_only)])

READERS = (sample.FRONTLINE, sample.SENIOR, sample.VIEW_IDENTIFIABLE)


@router.get("/plans/{pid}", name="supportlogs_plan")
def plan_detail(request: Request, pid: str) -> Response:
    """A plan (§7, §8): its owner's, a senior's who may convert a follow-up
    to a formal assignment, or Other Staff identifiable view's, read-only
    (the page map's Plans). A plan the viewer may not see is not found."""
    me = sample.viewer(request.query_params.get("as"))
    if not sample.holds(me, *READERS):
        return gated(request, "supportlogs/plan.html", *READERS)  # the 403 page
    found = sample.plan(pid)
    oversees = sample.holds(me, sample.SENIOR, sample.VIEW_IDENTIFIABLE)
    if found is None or not (oversees or sample.may_read_plan(me.name, found)):
        raise HTTPException(status_code=404)
    owner = found.staff == me.name
    return gated(
        request, "supportlogs/plan.html", *READERS,
        p=found, owner=owner, senior=sample.holds(me, sample.SENIOR),
        shared=not owner and not oversees,
        linked=sample.holds(me, sample.FRONTLINE) and reaches_student(me, found.student),
        current_tab="/plans/" if owner else "/students/" if not oversees else "/overview/",
    )


def owns_records(me: sample.Viewer, sid: str) -> bool:
    """The viewer has records of their own for the student to share."""
    return any(s.id == sid for s, _, _ in sample.working_set(me.name))


def share_choices(me: sample.Viewer, sid: str) -> list[str]:
    """Frontline colleagues to share with: not the viewer, not someone who
    already holds the grant, not a colleague who shared the student with
    the viewer."""
    taken = {g.viewer for g in sample.grants_by(me.name, sid)} | {g.grantor for g in sample.shared_with(me.name) if g.student == sid}
    return [c for c in sample.FRONTLINE_COLLEAGUES if c != me.name and c not in taken]


def _referable(me: sample.Viewer, sid: str) -> bool:
    """Not on the viewer's formal assignment, and not flagged already."""
    return not any(p.formal for p in sample.plans_of(me.name, sid)) and sample.referral(sid) is None


def _student_for(request: Request, sid: str) -> tuple[sample.Viewer, sample.Student | None]:
    me = sample.viewer(request.query_params.get("as"))
    found = sample.student(sid)
    if sample.holds(me, sample.FRONTLINE) and (found is None or not reaches_student(me, sid)):
        raise HTTPException(status_code=404)
    return me, found


@router.get("/students/{sid}/share", name="supportlogs_share")
def share(request: Request, sid: str) -> Response:
    """Share with a colleague (§11.1): the viewer's records for this
    student, with one frontline colleague."""
    me, found = _student_for(request, sid)
    if sample.holds(me, sample.FRONTLINE) and not owns_records(me, sid):
        raise HTTPException(status_code=404)  # nothing of the viewer's own to share
    colleagues = share_choices(me, sid)
    return gated(request, "supportlogs/share.html", sample.FRONTLINE, chosen=found, colleagues=colleagues,
                 current_tab="/students/")


@router.get("/students/{sid}/share/sent", name="supportlogs_share_sent")
def share_sent(request: Request, sid: str) -> Response:
    me, found = _student_for(request, sid)
    colleague = request.query_params.get("colleague")
    if sample.holds(me, sample.FRONTLINE) and not owns_records(me, sid):
        raise HTTPException(status_code=404)
    if sample.holds(me, sample.FRONTLINE) and colleague not in share_choices(me, sid):
        return RedirectResponse(url_path(request, f"/students/{sid}/share") + query(me), status_code=303)
    return gated(request, "supportlogs/share_sent.html", sample.FRONTLINE, chosen=found, colleague=colleague,
                 current_tab="/students/")


@router.get("/students/{sid}/refer", name="supportlogs_refer")
def refer(request: Request, sid: str) -> Response:
    """Flag for formal assignment (§3.1): no reason asked, only a suggested
    cadence for senior staff to weigh (§7.5)."""
    me, found = _student_for(request, sid)
    if sample.holds(me, sample.FRONTLINE) and not _referable(me, sid):
        return RedirectResponse(url_path(request, f"/students/{sid}") + query(me), status_code=303)
    return gated(request, "supportlogs/refer.html", sample.FRONTLINE, chosen=found, current_tab="/students/")


@router.get("/students/{sid}/refer/sent", name="supportlogs_refer_sent")
def refer_sent(request: Request, sid: str) -> Response:
    me, found = _student_for(request, sid)
    if sample.holds(me, sample.FRONTLINE) and not _referable(me, sid):
        return RedirectResponse(url_path(request, f"/students/{sid}") + query(me), status_code=303)
    cadence = request.query_params.get("cadence", "")
    cadence = cadence if cadence in sample.ASSIGNMENT_CADENCES else ""
    return gated(request, "supportlogs/refer_sent.html", sample.FRONTLINE, chosen=found, cadence=cadence,
                 current_tab="/students/")
