"""Support Logs' record downloads on sample data, segment 1D item 1 (author,
2026-10-30). Rung 7, Your records: the viewer's own encounters or plans
as CSV, for one term or all, and an empty template to fill for an upload.
Rung 8, Records across staff: senior identifiable access downloads staff
members' records by staff, student and term, and filters purged records by staff
and student for deletion: senior
staff's alone. Only a holder who has unlocked the section gets a file; anyone
else goes back to the locked page. Uploads, purges and deletions wait on
item 3; a purge only hides. A sample: the unlock rides in the address,
so wired, the unlock is held server-side and the download is a POST, so
no link or bookmark can start an audited export."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.pages import forbidden, gated, query, records_unlocked
from residentialapps.web.pages import placeholders_local_only
from residentialapps.web.urls import url_path

router = APIRouter(dependencies=[Depends(placeholders_local_only)])

UNKNOWN = "?"  # a staff name or student id that is no one's: never widened to all

KINDS = {
    "students": ("encounters", sample.ENCOUNTER_COLUMNS, sample.encounter_rows),
    "plans": ("plans", sample.PLAN_COLUMNS, sample.plan_rows),
}
TEMPLATES = {"students": sample.ENCOUNTER_COLUMNS, "plans": sample.PLAN_TEMPLATE_COLUMNS}


def _cell(value: str) -> str:
    """A cell a spreadsheet will not run: text that opens like a formula
    is kept as text, behind a leading apostrophe the upload (item 3) must
    strip."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def _csv(name: str, columns: tuple[str, ...], rows: list[list[str]]) -> Response:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(columns)
    writer.writerows([_cell(v) for v in row] for row in rows)
    return Response(out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


def _student(request: Request) -> str | None:
    """The chosen student's id; None for every student, chosen as an empty
    value; UNKNOWN for an id that is no student's."""
    key = request.query_params.get("student", "")
    if not key:
        return None
    return key if sample.student(key) else UNKNOWN


def _download(request: Request, page: str, template: bool) -> Response:
    me = sample.viewer(request.query_params.get("as"))
    if not sample.holds(me, sample.FRONTLINE):
        return forbidden(request, me)
    sid = _student(request)
    if not records_unlocked(request) or sid == UNKNOWN:
        return RedirectResponse(url_path(request, f"/{page}/") + query(me), status_code=303)
    what, columns, rows_of = KINDS[page]
    if template:
        return _csv(f"support-logs-{what}-template.csv", TEMPLATES[page], [])
    key = request.query_params.get("term", sample.CURRENT_TERM.key)
    chosen = None if key == "all" else sample.term(key) or sample.CURRENT_TERM
    scope = ("all-terms" if chosen is None else chosen.key) + (f"-{sid}" if sid else "")
    return _csv(f"support-logs-{what}-{scope}.csv", columns, rows_of(me.name, chosen, sid))


@router.get("/students/records.csv", name="supportlogs_students_records")
def encounters_csv(request: Request) -> Response:
    """Your encounters, for a term or all (§11.3: the download is recorded)."""
    return _download(request, "students", template=False)


@router.get("/students/records-template.csv", name="supportlogs_students_template")
def encounters_template(request: Request) -> Response:
    return _download(request, "students", template=True)


@router.get("/plans/records.csv", name="supportlogs_plans_records")
def plans_csv(request: Request) -> Response:
    """Your plans, for a term or all."""
    return _download(request, "plans", template=False)


@router.get("/plans/records-template.csv", name="supportlogs_plans_template")
def plans_template(request: Request) -> Response:
    return _download(request, "plans", template=True)


# --- Records across staff (rung 8; author, 2026-10-30): senior
# identifiable access only, behind the same lock.

def _staff(request: Request) -> str | None:
    """The chosen staff member; None for all staff, chosen as an empty
    value; UNKNOWN for a name that is not a staff member's."""
    name = request.query_params.get("staff", "")
    if not name:
        return None
    return name if name in sample.FRONTLINE_COLLEAGUES else UNKNOWN


def _term(request: Request, default: str) -> sample.Term | None:
    """The chosen term; None for all terms, chosen as "all". A missing key
    reads as `default`; an unknown one as the current term, never as all."""
    key = request.query_params.get("term", default)
    return None if key == "all" else sample.term(key) or sample.CURRENT_TERM


def _what(request: Request) -> str:
    what = request.query_params.get("what", "encounters")
    return what if what in sample.RECORD_KINDS else "encounters"


@router.get("/overview/records", name="supportlogs_overview_records")
def staff_records(request: Request) -> Response:
    """Records across staff: upload tagged to a staff member, download by
    staff, student and term, delete purged records by staff and student; by
    student, only that student's records go. Each action is a support-activity event
    (§11.3)."""
    staff, student = _staff(request), _student(request)
    purged = [] if UNKNOWN in (staff, student) else sample.purges(staff, student)  # unknown matches no one
    return gated(request, "supportlogs/overview_records.html", sample.SENIOR, current_tab="/overview/",
                 unlocked=records_unlocked(request), staff=staff, student=student, purged=purged,
                 purged_records=sum(p.about(None if student in (None, UNKNOWN) else student) for p in purged))


def _senior_download(request: Request, template: bool) -> Response:
    me = sample.viewer(request.query_params.get("as"))
    if not sample.holds(me, sample.SENIOR):
        return forbidden(request, me)
    if not records_unlocked(request):
        return RedirectResponse(url_path(request, "/overview/records") + query(me), status_code=303)
    what = _what(request)
    if template:
        return _csv(f"support-logs-{what}-staff-template.csv", ("Staff", *sample.STAFF_TEMPLATE_COLUMNS[what]), [])
    staff, chosen, sid = _staff(request), _term(request, sample.CURRENT_TERM.key), _student(request)
    if UNKNOWN in (staff, sid):  # a name or id that is no one's downloads nothing
        return RedirectResponse(url_path(request, "/overview/records") + query(me, records="open", understood="yes"),
                                status_code=303)
    columns, rows = sample.staff_rows(what, staff, chosen, sid)
    who = "all-staff" if staff is None else staff.lower().replace(" ", "-")
    scope = ("all-terms" if chosen is None else chosen.key) + (f"-{sid}" if sid else "")
    return _csv(f"support-logs-{what}-{who}-{scope}.csv", columns, rows)


@router.get("/overview/records.csv", name="supportlogs_overview_records_csv")
def staff_records_csv(request: Request) -> Response:
    return _senior_download(request, template=False)


@router.get("/overview/records-template.csv", name="supportlogs_overview_records_template")
def staff_records_template(request: Request) -> Response:
    return _senior_download(request, template=True)
