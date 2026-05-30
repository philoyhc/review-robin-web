"""Reviewer per-session participation-summary surface.

Segment 17B Phase 2 PR B. Carries:

- ``GET /me/sessions/{id}/summary`` — read-only HTML
  summary with one section per instrument the reviewer
  responded on. Gated on having submitted every assigned row;
  otherwise redirects back to the dashboard.
- ``GET /me/sessions/{id}/summary.csv`` —
  ``{code}_my_responses.csv`` download, reuses the 18H Part 2
  per-instrument extract infrastructure scoped to one reviewer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session
from starlette import status

from app.db.models import Reviewer, ReviewSession, User
from app.db.session import get_db
from app.services import responses as responses_service
from app.services import session_lifecycle as lifecycle
from app.services import sessions as sessions_service
from app.services.date_formatting import format_datetime, gmt_offset_zone_label
from app.services.extracts import filename, stream_csv
from app.services.extracts.responses_extract import (
    serialize_reviewer_session_summary,
)
from app.web import breadcrumbs
from app.web.deps import get_or_create_user, require_reviewer_in_session
from app.web.routes_reviewer._shared import (
    _templates,
    reviewer_review_count_for_user,
)
from app.web.views._reviewer_summary import build_reviewer_summary_context

router = APIRouter(prefix="/me")


def _is_session_fully_submitted(
    db: Session, *, reviewer: Reviewer, session_id: int
) -> bool:
    """Whether every row the reviewer is assigned has been
    submitted. Drives the summary route's gate and the
    submit-flow's redirect-to-summary decision."""
    state = responses_service.reviewer_session_state(
        db, reviewer=reviewer, session_id=session_id
    )
    return (
        state.total_assignments > 0
        and state.pill_state == "submitted"
    )


@router.get(
    "/sessions/{session_id}/summary",
    response_class=HTMLResponse,
    response_model=None,
)
def reviewer_session_summary(
    request: Request,
    reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    reviewer, review_session = reviewer_session
    if not _is_session_fully_submitted(
        db, reviewer=reviewer, session_id=review_session.id
    ):
        # Not all rows submitted — redirect to the dashboard.
        return RedirectResponse(
            url="/me",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    summary = build_reviewer_summary_context(
        db, review_session=review_session, reviewer=reviewer
    )
    session_zone = sessions_service.resolve_session_timezone(review_session)
    return _templates.TemplateResponse(
        request,
        "reviewer/summary.html",
        {
            "user": user,
            "session": review_session,
            "summary": summary,
            "submitted_at_text": (
                format_datetime(summary.last_submitted_at, session_zone)
                if summary.last_submitted_at
                else None
            ),
            "submitted_at_zone_label": (
                gmt_offset_zone_label(
                    session_zone, at=summary.last_submitted_at
                )
                if summary.last_submitted_at
                else None
            ),
            "breadcrumbs": breadcrumbs.reviewer_session(review_session),
            "reviewer_review_count": reviewer_review_count_for_user(
                db, user
            ),
            # ``Recall my submission`` button is shown only while
            # the session is ``ready`` — recall would have no live
            # form to land on once the operator closes the session
            # (``expired``) or reverts it (``draft``).
            "can_recall": lifecycle.is_ready(review_session),
        },
    )


@router.get("/sessions/{session_id}/summary.csv", response_model=None)
def reviewer_session_summary_csv(
    reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> StreamingResponse | RedirectResponse:
    reviewer, review_session = reviewer_session
    if not _is_session_fully_submitted(
        db, reviewer=reviewer, session_id=review_session.id
    ):
        return RedirectResponse(
            url="/me",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    download_name = filename(review_session, "my_responses")
    return StreamingResponse(
        stream_csv(
            serialize_reviewer_session_summary(
                db, review_session, reviewer
            )
        ),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{download_name}"'
            )
        },
    )
