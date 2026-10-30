"""Support Logs' Your records downloads on sample data, segment 1D item 1
rung 7 (author, 2026-10-30): the viewer's own encounters or plans as CSV,
for one term or all, and an empty template to fill for an upload. Only a
holder who has unlocked the section gets a file; anyone else goes back to
the locked page. Uploads and purges wait on item 3; a purge only hides,
and a sys admin alone deletes."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.pages import forbidden, query, records_unlocked
from residentialapps.web.pages import placeholders_local_only
from residentialapps.web.urls import url_path

router = APIRouter(dependencies=[Depends(placeholders_local_only)])

KINDS = {
    "students": ("encounters", sample.ENCOUNTER_COLUMNS, sample.encounter_rows),
    "plans": ("plans", sample.PLAN_COLUMNS, sample.plan_rows),
}


def _cell(value: str) -> str:
    """A cell a spreadsheet will not run: text that opens like a formula
    is kept as text."""
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
        return _csv(f"support-logs-{what}-template.csv", columns, [])
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
