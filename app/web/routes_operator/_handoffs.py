"""Handoffs from another Cordware application (segment 23A).

The proof of concept's RRW side: a holding page that another
application opens in a new tab during its operator's click, while it
posts the setup that creates the session, then moves the tab to that
session's Session Home (`cordware/docs/cordware_interoperability_consolidated_spec_v0.3.md`
§7.1). The create route itself is in ``_quick_setup.py``, whose
pipeline it runs (slices do not import one another).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.services import handoffs
from app.web import breadcrumbs, urls
from app.web.deps import get_or_create_user
from app.web.downloads import content_disposition
from app.web.routes_operator._shared import _templates

router = APIRouter()

#: Never cached: the page stands in while a session is created.
_NO_STORE = {"Cache-Control": "no-store"}


@router.get("/handoffs/new", response_class=HTMLResponse)
def handoff_holding(request: Request, user: User = Depends(get_or_create_user)) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "operator/handoff_new.html",
        {"user": user, "breadcrumbs": breadcrumbs.operator_sessions_child("New session")},
        headers=_NO_STORE,
    )


def _refused(request: Request, exc: handoffs.HandoffError) -> JSONResponse:
    body: dict[str, object] = {"error": exc.code}
    if exc.details:
        body["details"] = exc.details
    if exc.review_session is not None:
        body["session_home_url"] = urls.url_path(
            request, f"/operator/sessions/{exc.review_session.public_id}"
        )
    return JSONResponse(body, status_code=exc.status, headers=_NO_STORE)


@router.get("/handoffs/{transfer_id}/status", response_model=None)
def handoff_status(
    request: Request,
    transfer_id: str,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """A handed-off session's live status, for the sender that made it
    (segment 23B; `spec/handoffs.md`). JSON, ``no-store``, read only."""
    try:
        review_session = handoffs.linked(db, user, transfer_id)
    except handoffs.HandoffError as exc:
        return _refused(request, exc)
    body = handoffs.status(db, review_session)
    body["session_home_url"] = urls.url_path(
        request, f"/operator/sessions/{review_session.public_id}"
    )
    return JSONResponse(body, headers=_NO_STORE)


def _csv(
    request: Request,
    transfer_id: str,
    user: User,
    db: Session,
    build: Callable[[Session, ReviewSession], handoffs.CsvSnapshot],
) -> Response:
    try:
        review_session = handoffs.linked(db, user, transfer_id)
    except handoffs.HandoffError as exc:
        return _refused(request, exc)
    snapshot = build(db, review_session)
    headers = {
        **_NO_STORE,
        "ETag": snapshot.etag,
        "X-Review-Robin-As-Of": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    # Already up to date (interop spec §6.5): nothing taken, nothing audited.
    if request.headers.get("if-none-match") == snapshot.etag:
        return Response(status_code=304, headers=headers)
    handoffs.record_export(db, review_session, user, transfer_id, snapshot)
    headers["Content-Disposition"] = content_disposition(f"{review_session.code}_{snapshot.name}")
    return Response(snapshot.body, media_type="text/csv; charset=utf-8", headers=headers)


@router.get("/handoffs/{transfer_id}/results.csv", response_model=None)
def handoff_results(
    request: Request,
    transfer_id: str,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> Response:
    """The submitted answers of a handed-off session, for its sender
    (segment 23B; `spec/handoffs.md`). Audited as an export."""
    return _csv(request, transfer_id, user, db, handoffs.results_csv)


@router.get("/handoffs/{transfer_id}/completion.csv", response_model=None)
def handoff_completion(
    request: Request,
    transfer_id: str,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> Response:
    """Where each assignment of a handed-off session stands, for its
    sender (segment 23B). No answers. Audited as an export."""
    return _csv(request, transfer_id, user, db, handoffs.completion_csv)
