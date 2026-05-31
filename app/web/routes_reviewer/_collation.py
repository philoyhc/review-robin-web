"""Observer collation surface — ``GET /me/sessions/{id}/collation``.

Placeholder shell that lights up the URL behind
``require_observer_in_session``: an observer whose ``email``
(case-insensitive) matches the authenticated user's email
reaches the page; everyone else gets 403 / 404 from the gate.
Today the body is just the chrome — the cross-reviewee
collation render lands with W17 per
``guide/participant_model_upgrade.md`` §3.2.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.models import Observer, ReviewSession, User
from app.db.session import get_db
from app.web.deps import get_or_create_user, require_observer_in_session
from app.web.routes_reviewer._shared import (
    _templates,
    build_role_chips,
    reviewer_review_count_for_user,
)

router = APIRouter(prefix="/me")


@router.get(
    "/sessions/{session_id}/collation",
    response_class=HTMLResponse,
)
def observer_collation(
    request: Request,
    observer_session: tuple[Observer, ReviewSession] = Depends(
        require_observer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    _observer, review_session = observer_session
    return _templates.TemplateResponse(
        request,
        "reviewer/collation.html",
        {
            "user": user,
            "session": review_session,
            "reviewer_review_count": reviewer_review_count_for_user(
                db, user
            ),
            "role_chips": build_role_chips(
                db,
                user=user,
                review_session=review_session,
                active_role="observer",
            ),
        },
    )
