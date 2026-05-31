"""Setup-Observers page route — placeholder surface for the
participant-model Observer roster (Phase 2 placeholder per
``guide/participant_model_prep.md`` P1).

The page renders four cards in a two-column layout — Observers
list + Upload observers on the left; Operator actions + Danger
zone on the right — all visible but inert. CSV import / single-
row authoring / bulk status flips wire up in the Observer
roster slice (W10).

Route-gated on ``session.observers_enabled``
(``require_observers_enabled_session``) so the page 404s until
the operator opts in via the User interface settings card on
Session Edit Details.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, ReviewSession, User
from app.db.session import get_db
from app.web import breadcrumbs, views
from app.web.deps import get_or_create_user
from app.web.routes_operator._shared import (
    _templates,
    require_observers_enabled_session,
)


router = APIRouter()


@router.get(
    "/sessions/{session_id}/observers", response_class=HTMLResponse
)
def observers_page(
    request: Request,
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the placeholder Observers Setup page.

    Cards (CSV import, per-row add, bulk-status, delete-all) are
    inert here — the page exists so operators / designers can
    see the eventual shape of the Observer roster before the
    real wiring ships (W10).
    """
    observers = list(
        db.execute(
            select(Observer)
            .where(Observer.session_id == review_session.id)
            .order_by(Observer.email)
        ).scalars()
    )
    return _templates.TemplateResponse(
        request,
        "operator/session_observers.html",
        {
            "user": user,
            "session": review_session,
            "observers": observers,
            "status_pills": views.session_status_pills(
                db, review_session
            ),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Observers"
            ),
        },
    )
