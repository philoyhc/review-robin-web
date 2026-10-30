"""The Email Address Checker's pages (segment U1). Rung 2 built them as
placeholders on sample counts; rung 3 wires the upload and the preview
to `csvio`. The check, and the result page's real counts, land in rung 5.

Placeholders enforce no access rule yet, so they answer only on a local
run (`APP_ENV=local`) and are 404 deployed; rung 5 swaps this gate for the
super-admin one (spec §3)."""

from __future__ import annotations

import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import Response

from cordware.identity import is_local
from utilityapps.email_check import csvio
from utilityapps.web import templates

# The preview carries the upload back as base64 (plan, "No server state"),
# a third larger than the file; Starlette's default part limit is 1 MiB.
_FORM_PART_LIMIT = 2 * csvio.MAX_BYTES


def placeholders_local_only() -> None:
    if not is_local():
        raise HTTPException(status_code=404)


router = APIRouter(prefix="/email-check", dependencies=[Depends(placeholders_local_only)])

# The preview's sample file: a header with no `email` column, so the
# column choice shows (spec §4), and counts that exercise every line.
SAMPLE_HEADER = ("Name", "Work email", "Role")
SAMPLE_PREVIEW = csvio.Preview(rows=42, valid=38, invalid=2, repeated=2)
# The result's sample counts, one per status (spec §6), summing to 42.
SAMPLE_RESULT = {
    "OK": 27,
    "USE_PRIMARY": 6,
    "FOUND_NO_PRIMARY": 1,
    "NOT_FOUND": 3,
    "AMBIGUOUS": 1,
    "INVALID_INPUT": 2,
    "ERROR": 2,
}


@router.get("/", name="utilities_email_check")
def upload(request: Request) -> Response:
    return templates.TemplateResponse(request, "email_check/upload.html")


def _upload_error(request: Request, message: str) -> Response:
    return templates.TemplateResponse(
        request, "email_check/upload.html", {"error": message}, status_code=400
    )


@router.post("/preview", name="utilities_email_check_preview_post")
async def preview_post(request: Request) -> Response:
    """The upload's preview. From the upload page the file comes as
    `file`; from the preview itself, choosing a column, as `content`
    (base64) with `filename` and `column`. Nothing is kept between."""
    form = await request.form(max_part_size=_FORM_PART_LIMIT)
    file = form.get("file")
    if "file" in form and not (isinstance(file, UploadFile) and file.filename):
        # An untouched file input posts an empty-named part.
        return _upload_error(request, "Choose a CSV file first.")
    if isinstance(file, UploadFile):
        data = await file.read(csvio.MAX_BYTES + 1)
        filename = file.filename
    else:
        try:
            data = base64.b64decode(str(form.get("content", "")), validate=True)
        except (binascii.Error, ValueError):
            return _upload_error(request, "The file could not be carried over. Upload it again.")
        filename = str(form.get("filename", ""))
    try:
        upload = csvio.parse(data)
    except csvio.CsvRejected as exc:
        return _upload_error(request, str(exc))
    column = upload.email_column
    chosen = str(form.get("column", ""))
    if chosen.isdigit() and int(chosen) < len(upload.header):
        column = int(chosen)
    counts = csvio.preview(upload, column) if column is not None else None
    return templates.TemplateResponse(
        request,
        "email_check/preview.html",
        {
            "sample": False,
            "filename": filename,
            "header": upload.header,
            "column": column,
            "detected": upload.email_column is not None,
            "counts": counts,
            "content": base64.b64encode(data).decode("ascii"),
            "no_graph": False,
        },
    )


@router.get("/preview", name="utilities_email_check_preview")
def preview(request: Request) -> Response:
    # `?state=no-graph`: the preview as it reads when the directory cannot
    # be reached, so the copy can be judged before it is wired.
    no_graph = request.query_params.get("state") == "no-graph"
    return templates.TemplateResponse(
        request,
        "email_check/preview.html",
        {
            "sample": True,
            "filename": "sample-roster.csv",
            "header": SAMPLE_HEADER,
            "column": 1,
            "detected": False,
            "counts": SAMPLE_PREVIEW,
            "content": "",
            "no_graph": no_graph,
        },
    )


@router.get("/result", name="utilities_email_check_result")
def result(request: Request) -> Response:
    return templates.TemplateResponse(
        request,
        "email_check/result.html",
        {"counts": SAMPLE_RESULT, "total": sum(SAMPLE_RESULT.values()), "groups": 2},
    )
