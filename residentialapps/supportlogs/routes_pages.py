"""Support Logs' placeholder pages, segment 1D item 1 rung 1: every page
in the plan's list as a static placeholder naming the grant it needs, the
rung that builds it and what it will hold. Later rungs replace each with
its screen; items 2–5 wire them."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import Response

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.pages import SYS_ADMIN_AREA, page
from residentialapps.web.pages import placeholders_local_only

router = APIRouter(dependencies=[Depends(placeholders_local_only)])


@dataclass(frozen=True)
class Placeholder:
    path: str
    name: str  # the route name, after `supportlogs_`
    title: str
    grants: tuple[str, ...]
    rung: int
    holds: tuple[str, ...]  # what the page will hold, one line each, with its spec section
    area: str = "Support Logs"
    tab: str = ""  # the tab a page off the tab bar marks


PLACEHOLDERS = (
    Placeholder("/log", "log", "Log encounter", (sample.FRONTLINE,), 2, (
        "Student, duration and type on one screen, with the student's card once chosen (§5.1–5.6)",
        "Optional details on the same page: concern areas, follow-up needed, add to my follow-ups, how, who started it, a short note (§5.7–5.9)",
        "Save encounter at the form's end, disabled until the three required choices are made (§5.3)",
        "Mark a safety concern, set apart at the bottom (§5.10)",
    )),
    Placeholder("/log/safety", "log_safety", "Safety concern", (sample.FRONTLINE,), 3, (
        "Call actions first: emergency services, campus security, the counselling duty line, duty senior staff (§5.10)",
        "The encounter's context, the crisis protocol's steps and the escalation step taken",
        "Save and raise safety flag, and Cancel",
    ), tab="/log"),
    Placeholder("/students/", "students", "Students", (sample.FRONTLINE,), 2, (
        "Search as the signed-in staff member, with the email fallback (§4.2)",
        "My students first: plans, follow-ups and everyone I have logged an encounter with (§4.3)",
        "Each opening the student view, which says the view is recorded (§9, §11.3)",
    )),
    Placeholder("/plans/", "plans", "My plans", (sample.FRONTLINE,), 2, (
        "All, Overdue, This week",
        "Formal assignments first, with source and cadence, and the safety-plan marker (§7, §5.10)",
        "Then informal follow-ups (§6), and Add a student to follow up",
    )),
    Placeholder("/overview/", "overview", "Overview", (sample.SENIOR, *sample.VIEW), 5, (
        "Team workload with load weighting (§10.2–10.3)",
        "Hotspots and clusters (§10.4–10.5)",
        "Due and overdue coverage (§10.6), and every plan",
        "Safety flags, for those who receive them (§5.10)",
        "Other Staff view: counts only when aggregate; named drill-downs and plans, read-only, when identifiable",
    )),
    Placeholder("/consultation/", "consultation", "Consultation check", (sample.CONSULTATION,), 6, (
        "A purpose and a list of students' emails, for any approved purpose (§10.7)",
        "Each student: No consultation indicated, Consultation suggested or Consultation required, with the reasons, and whom to consult (§10.8)",
        "Consultation requested or done; past checks",
    )),
    Placeholder("/sys-admin/", "sys_admin", "Access", sample.ADMINISTRATION, 6, (
        "Every active Staff-roster member, read from Residential Operations as the eligibility list",
        "A toggle per authorization type, a reason and an audit event per change",
        "Lapsed grants first; Sys admin granted by the super-admin alone",
    ), area=SYS_ADMIN_AREA),
    Placeholder("/sys-admin/configuration", "sys_admin_configuration", "Configuration", sample.ADMINISTRATION, 6, (
        "The lists staff choose from: durations, encounter types, concern areas, modes, cadences (§5.5–5.9)",
        "Escalation steps and closure outcomes (§5.10)",
    ), area=SYS_ADMIN_AREA),
    Placeholder("/sys-admin/clusters", "sys_admin_clusters", "Clusters", sample.ADMINISTRATION, 6, (
        "The cluster list; which students belong to each is set by senior staff, not here (§10.5)",
    ), area=SYS_ADMIN_AREA),
    Placeholder("/sys-admin/audit", "sys_admin_audit", "Audit log", sample.ADMINISTRATION, 6, (
        "Administrative events only: grants, configuration and other administration (§11.3)",
        "No support content and no support-activity audit",
    ), area=SYS_ADMIN_AREA),
)


def _route(p: Placeholder):
    def show(request: Request) -> Response:
        return page(request, *p.grants, area=p.area, placeholder=p, current_tab=p.tab)

    return show


for _p in PLACEHOLDERS:
    router.add_api_route(_p.path, _route(_p), methods=["GET"], name=f"supportlogs_{_p.name}")
