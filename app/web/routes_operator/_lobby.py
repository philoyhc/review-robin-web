"""Sessions lobby — the operator's "all my sessions" page + bulk
delete from that page. Slice 1 of the major refactor.

Source ranges in pre-refactor ``routes_operator.py``: 64-123.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.services import sessions
from app.services import session_lifecycle as lifecycle
from app.web import breadcrumbs
from app.web.deps import get_or_create_user, request_correlation_id
from app.web.routes_operator._shared import _templates


router = APIRouter()


@router.get("/sessions", response_class=HTMLResponse)
def list_sessions(
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    review_sessions = sessions.list_for_user(db, user)
    return _templates.TemplateResponse(
        request,
        "operator/sessions_list.html",
        {
            "user": user,
            "sessions": review_sessions,
            "breadcrumbs": breadcrumbs.operator_root(),
        },
    )


@router.post("/sessions/delete-selected")
def sessions_delete_selected(
    session_ids: list[int] = Form(default=[]),
    confirm: str | None = Form(default=None),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Bulk-delete the sessions ticked on the operator sessions list.

    Filters server-side to caller-owned + editable (draft / validated)
    sessions; non-editable rows are silently skipped per the existing
    ``_require_editable`` posture. The Danger Zone card on the list
    page surfaces a confirm checkbox and an explicit destructive
    button — without ``confirm=true`` the request is rejected with
    ``400`` (matches the single-session ``/sessions/{id}/delete``
    handler). Each deletion goes through ``sessions.delete_session``
    which already cascades reviewers / reviewees / instruments /
    assignments / invitations / email_outbox rows + writes the
    ``session.deleted`` audit row."""

    if confirm != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm checkbox required",
        )
    correlation_id = request_correlation_id()
    for session_id in session_ids:
        review_session = sessions.get_for_user(db, user, session_id)
        if review_session is None:
            continue
        if not lifecycle.is_editable(review_session):
            continue
        sessions.delete_session(
            db,
            review_session=review_session,
            user=user,
            correlation_id=correlation_id,
        )
    return RedirectResponse(
        url="/operator/sessions",
        status_code=status.HTTP_303_SEE_OTHER,
    )
