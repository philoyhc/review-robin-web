"""Support Logs' Your records downloads on sample data, segment 1D item 1
rung 7 (author, 2026-10-30): the viewer's own encounters or plans as CSV,
for one term or all, and an empty template to fill for an upload. Only a
holder who has unlocked the section gets a file; anyone else goes back to
the locked page. Uploads and purges wait on item 3; a purge only hides,
and a sys admin alone deletes. A sample: the unlock rides in the address,
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


def _download(request: Request, page: str, template: bool) -> Response:
    me = sample.viewer(request.query_params.get("as"))
    if not sample.holds(me, sample.FRONTLINE):
        return forbidden(request, me)
    if not records_unlocked(request):
        return RedirectResponse(url_path(request, f"/{page}/") + query(me), status_code=303)
    what, columns, rows_of = KINDS[page]
    if template:
        return _csv(f"support-logs-{what}-template.csv", TEMPLATES[page], [])
    key = request.query_params.get("term", sample.CURRENT_TERM.key)
    chosen = None if key == "all" else sample.term(key) or sample.CURRENT_TERM
    scope = "all-terms" if chosen is None else chosen.key
    return _csv(f"support-logs-{what}-{scope}.csv", columns, rows_of(me.name, chosen))


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
    """The chosen staff member, or None for all staff (an unknown name
    reads as all)."""
    name = request.query_params.get("staff", "")
    return name if name in sample.FRONTLINE_COLLEAGUES else None


def _term(request: Request) -> sample.Term | None:
    key = request.query_params.get("term", "all")
    return None if key == "all" else sample.term(key)


def _what(request: Request) -> str:
    what = request.query_params.get("what", "encounters")
    return what if what in sample.RECORD_KINDS else "encounters"


@router.get("/overview/records", name="supportlogs_overview_records")
def staff_records(request: Request) -> Response:
    """Records across staff: upload tagged to a staff member, download by
    staff and term, delete purged records by staff and term. Each action
    is a support-activity event (§11.3)."""
    staff, chosen = _staff(request), _term(request)
    return gated(request, "supportlogs/overview_records.html", sample.SENIOR, current_tab="/overview/",
                 unlocked=records_unlocked(request), staff=staff, chosen=chosen,
                 purged=sample.purges(staff, chosen))


def _senior_download(request: Request, template: bool) -> Response:
    me = sample.viewer(request.query_params.get("as"))
    if not sample.holds(me, sample.SENIOR):
        return forbidden(request, me)
    if not records_unlocked(request):
        return RedirectResponse(url_path(request, "/overview/records") + query(me), status_code=303)
    what = _what(request)
    if template:
        return _csv(f"support-logs-{what}-staff-template.csv", ("Staff", *sample.RECORD_KINDS[what][1]), [])
    staff, chosen = _staff(request), _term(request)
    columns, rows = sample.staff_rows(what, staff, chosen)
    who = "all-staff" if staff is None else staff.lower().replace(" ", "-")
    scope = "all-terms" if chosen is None else chosen.key
    return _csv(f"support-logs-{what}-{who}-{scope}.csv", columns, rows)


@router.get("/overview/records.csv", name="supportlogs_overview_records_csv")
def staff_records_csv(request: Request) -> Response:
    return _senior_download(request, template=False)


@router.get("/overview/records-template.csv", name="supportlogs_overview_records_template")
def staff_records_template(request: Request) -> Response:
    return _senior_download(request, template=True)
