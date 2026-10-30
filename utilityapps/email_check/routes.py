"""The Email Address Checker's three pages, as placeholders (segment U1,
rung 2): real copy and layout, inert controls, sample counts. The checker
behind them lands in rungs 3–5.

Placeholders enforce no access rule yet, so they answer only on a local
run (`APP_ENV=local`) and are 404 deployed; rung 5 swaps this gate for the
super-admin one (spec §3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request
from starlette.responses import Response

from cordware.identity import is_local
from utilityapps.web import templates


def placeholders_local_only() -> None:
    if not is_local():
        raise HTTPException(status_code=404)


router = APIRouter(prefix="/email-check", dependencies=[Depends(placeholders_local_only)])

# The preview's sample file: a header with no `email` column, so the
# column choice shows (spec §4), and counts that exercise every line.
SAMPLE_HEADER = ("Name", "Work email", "Role")
SAMPLE_PREVIEW = {"rows": 42, "valid": 38, "invalid": 2, "repeated": 2}
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


@router.get("/preview", name="utilities_email_check_preview")
def preview(request: Request) -> Response:
    # `?state=no-graph`: the preview as it reads when the directory cannot
    # be reached, so the copy can be judged before it is wired.
    no_graph = request.query_params.get("state") == "no-graph"
    return templates.TemplateResponse(
        request,
        "email_check/preview.html",
        {"header": SAMPLE_HEADER, "counts": SAMPLE_PREVIEW, "no_graph": no_graph},
    )


@router.get("/result", name="utilities_email_check_result")
def result(request: Request) -> Response:
    return templates.TemplateResponse(
        request,
        "email_check/result.html",
        {"counts": SAMPLE_RESULT, "total": sum(SAMPLE_RESULT.values()), "groups": 2},
    )
