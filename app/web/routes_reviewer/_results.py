"""Reviewee results surface — ``GET /me/sessions/{id}/results``.

Gated by ``require_reviewee_in_session``: a reviewee whose
``email_or_identifier`` (case-insensitive) matches the
authenticated user's email reaches the page; everyone else
gets 403 / 404 from the gate.

Body content is the reviewee's view of the responses written
about them on this session, filtered through the per-instrument
visibility policy
(``app/services/visibility_policies.py``). This slice ships the
``"raw"`` mode — instruments whose ``reviewee`` policy resolves
to Raw render one row per reviewer who responded; other modes
(``anonymized`` / ``summarized``) and the observer surface
ship in follow-on slices. Empty body when no instrument has a
currently-active grant for the signed-in reviewee.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.models import Reviewee, ReviewSession, User
from app.db.session import get_db
from app.web.deps import get_or_create_user, require_reviewee_in_session
from app.web.routes_reviewer._shared import (
    _templates,
    build_role_chips,
    reviewer_review_count_for_user,
)
from app.web.views._reviewee_results import build_reviewee_results_context

router = APIRouter(prefix="/me")


@router.get(
    "/sessions/{session_id}/results",
    response_class=HTMLResponse,
)
def reviewee_results(
    request: Request,
    reviewee_session: tuple[Reviewee, ReviewSession] = Depends(
        require_reviewee_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    reviewee, review_session = reviewee_session
    context = build_reviewee_results_context(
        db, review_session=review_session, reviewee=reviewee
    )
    return _templates.TemplateResponse(
        request,
        "reviewer/results.html",
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
                active_role="reviewee",
            ),
            "sections": context.sections,
        },
    )
