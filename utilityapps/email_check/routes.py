"""The Email Address Checker's pages (`utilityapps/spec/email_check.md`;
segment U1). Upload, preview, check, result: nothing is kept between
steps. The preview carries the file back as base64 in the page, and the
result carries the checked CSV as its download.

Every route is the platform super-admin's alone (spec §3): anyone else
signed in gets a plain `403`.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
from dataclasses import dataclass
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.datastructures import FormData, UploadFile
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from cordware.graph import GraphError, directory_for
from cordware.identity import resolve_identity
from utilityapps.email_check import check, csvio
from utilityapps.web import templates, url_path

log = logging.getLogger(__name__)

# Request sizes, refused on `Content-Length` before anything is parsed
# (diff-reviewer, `#3411`). The upload is multipart, and a file part has
# no size limit in Starlette: past 1 MiB it is spooled to a temporary
# file. So the whole request is held to `MAX_BYTES`, which keeps the file
# in memory and refuses it unread. The preview carries the file back
# URL-encoded, as base64 a third larger, with no file part to spool, and
# from segment U2 with the outcomes the page's batches collected.
_UPLOAD_LIMIT = csvio.MAX_BYTES
_CARRIED_LIMIT = 3 * csvio.MAX_BYTES
# One batch of keys from the page (segment U2).
_LOOKUP_LIMIT = 16 * 1024
_FORM_PART_LIMIT = _CARRIED_LIMIT
# Results hold names and addresses: never cached anywhere (spec §10).
_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def require_super_admin(request: Request) -> None:
    identity = resolve_identity(request)  # 401 with no identity
    if not identity.is_super_admin:
        raise HTTPException(status_code=403)


router = APIRouter(prefix="/email-check", dependencies=[Depends(require_super_admin)])


def _page(request: Request, name: str, context: dict | None = None, status: int = 200) -> Response:
    return templates.TemplateResponse(request, name, context or {}, status_code=status, headers=_NO_STORE)


@router.get("/", name="utilities_email_check")
def upload(request: Request) -> Response:
    return _page(request, "email_check/upload.html")


def _upload_error(request: Request, message: str) -> Response:
    return _page(request, "email_check/upload.html", {"error": message}, status=400)


@dataclass(frozen=True)
class _Posted:
    data: bytes
    filename: str
    upload: csvio.Upload
    column: int | None
    #: The page's collected outcomes and why its batches stopped, if they
    #: did (segment U2): absent when the page posted without its script.
    outcomes: str | None = None
    stopped: str = ""


async def _read(request: Request) -> _Posted | Response:
    """The file a step posted: as `file` from the upload page, or carried
    as `content` (base64) with `filename` and `column` from the preview."""
    length = request.headers.get("content-length", "")
    multipart = request.headers.get("content-type", "").startswith("multipart/")
    limit = _UPLOAD_LIMIT if multipart else _CARRIED_LIMIT
    if not length.isdecimal():
        return _upload_error(request, "The upload did not say its size. Upload the file again.")
    if int(length) > limit:
        return _upload_error(request, f"The file is larger than {csvio.MAX_BYTES // 1024} KiB.")
    try:
        form: FormData = await request.form(max_part_size=_FORM_PART_LIMIT)
    except StarletteHTTPException:
        return _upload_error(request, "The upload could not be read. Upload the file again.")
    file = form.get("file")
    if "file" in form and not (isinstance(file, UploadFile) and file.filename):
        # An untouched file input posts an empty-named part.
        return _upload_error(request, "Choose a CSV file first.")
    if isinstance(file, UploadFile):
        data = await file.read(csvio.MAX_BYTES + 1)
        filename = file.filename or ""
    else:
        try:
            data = base64.b64decode(str(form.get("content", "")), validate=True)
        except (binascii.Error, ValueError):
            return _upload_error(request, "The file could not be carried over. Upload it again.")
        filename = str(form.get("filename", ""))
    try:
        parsed = csvio.parse(data)
    except csvio.CsvRejected as exc:
        return _upload_error(request, str(exc))
    column = parsed.email_column
    chosen = str(form.get("column", ""))
    # `isdecimal`, not `isdigit`: "²" is a digit `int` refuses (diff-reviewer).
    if chosen.isdecimal() and int(chosen) < len(parsed.header):
        column = int(chosen)
    outcomes = form.get("outcomes")
    return _Posted(
        data,
        filename,
        parsed,
        column,
        outcomes=outcomes if isinstance(outcomes, str) else None,
        stopped=str(form.get("stopped", "")),
    )


def _preview(request: Request, posted: _Posted, *, no_graph: bool = False) -> Response:
    counts = csvio.preview(posted.upload, posted.column) if posted.column is not None else None
    return _page(
        request,
        "email_check/preview.html",
        {
            "filename": posted.filename,
            "header": posted.upload.header,
            "column": posted.column,
            "detected": posted.upload.email_column is not None,
            "counts": counts,
            "content": base64.b64encode(posted.data).decode("ascii"),
            "no_graph": no_graph,
        },
        status=503 if no_graph else 200,
    )


@router.post("/preview", name="utilities_email_check_preview")
async def preview(request: Request) -> Response:
    posted = await _read(request)
    return posted if isinstance(posted, Response) else _preview(request, posted)


@router.post("/check", name="utilities_email_check_check")
async def run_check(request: Request) -> Response:
    posted = await _read(request)
    if isinstance(posted, Response):
        return posted
    if posted.column is None:
        return _preview(request, posted)
    if posted.outcomes is not None:
        # The page's batches already looked every key up (segment U2).
        keys = csvio.preview(posted.upload, posted.column).keys
        try:
            carried = check.outcomes_from_json(json.loads(posted.outcomes), keys)
        except (ValueError, RecursionError):
            return _upload_error(request, "The check's results could not be read. Upload the file again.")
        result = check.run(posted.upload, posted.column, None, carried=carried, stopped=posted.stopped)
    else:
        try:
            directory = directory_for(request)
        except GraphError:
            # No delegated token: say so, and check nothing (spec §3).
            return _preview(request, posted, no_graph=True)
        result = await run_in_threadpool(check.run, posted.upload, posted.column, directory)
    # Counts and failure kinds only: never an address, a name or an id.
    log.info(
        "email check completed",
        extra={
            "event": "email_check.completed",
            "rows": result.rows,
            "lookups": result.lookups,
            "counts": result.counts,
            "groups": result.groups,
            "error_kinds": list(result.error_kinds),
        },
    )
    return _page(
        request,
        "email_check/result.html",
        {
            "result": result,
            "download": "data:text/csv;charset=utf-8;base64,"
            + base64.b64encode(("﻿" + result.csv).encode("utf-8")).decode("ascii"),
            "download_name": f"email-check-results-{date.today():%Y%m%d}.csv",
        },
    )


def _lookup_error(status: int, error: str) -> JSONResponse:
    return JSONResponse({"error": error}, status_code=status, headers=_NO_STORE)


@router.post("/lookup", name="utilities_email_check_lookup")
async def lookup(request: Request) -> Response:
    """One batch of the page's check (segment U2): ``{"keys": [...]}`` in,
    ``{"outcomes": {key: outcome}}`` out. JSON only, so a cross-site form
    cannot post it without a preflight."""
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        return _lookup_error(415, "json_required")
    length = request.headers.get("content-length", "")
    if not length.isdecimal() or int(length) > _LOOKUP_LIMIT:
        return _lookup_error(413, "too_large")
    try:
        body = json.loads(await request.body())
    except (ValueError, RecursionError):
        return _lookup_error(400, "bad_json")
    keys = body.get("keys") if isinstance(body, dict) else None
    if (
        not isinstance(keys, list)
        or not 1 <= len(keys) <= check.BATCH_MAX
        or not all(isinstance(k, str) and csvio.lookup_key(k) == k for k in keys)
    ):
        return _lookup_error(400, "bad_keys")
    try:
        directory = directory_for(request)
    except GraphError:
        return _lookup_error(503, "no_graph")
    outcomes = await run_in_threadpool(
        check.look_up_all, directory, keys, budget=check.BATCH_BUDGET
    )
    return JSONResponse(
        {"outcomes": {k: check.outcome_json(o) for k, o in outcomes.items()}}, headers=_NO_STORE
    )


# A step reached by its address rather than a post starts again.
@router.get("/preview", include_in_schema=False)
@router.get("/check", include_in_schema=False)
def start_again(request: Request) -> Response:
    return RedirectResponse(url_path(request, "/email-check/"), status_code=303)
