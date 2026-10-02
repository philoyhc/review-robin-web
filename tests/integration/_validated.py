"""Promote a test session ``draft → validated`` through the service.

Tests used to reach ``validated`` with ``GET …/assignments?validated=1``,
a promotion path no page linked to; it was retired (2026-10-02, findings
B15). This does what that path did: run validation, and when the report
is clean and the session is still a draft, call
``session_lifecycle.mark_validated`` as the session's creator. Otherwise
it is a no-op, as the path was.
"""
from __future__ import annotations

from sqlalchemy.orm import Session, object_session

from app.db.models import ReviewSession
from app.services import session_lifecycle as lifecycle
from app.services import validation


def validate_session(
    target: ReviewSession | Session, session_id: int | None = None
) -> None:
    """``validate_session(review_session)`` or ``validate_session(db, id)``."""
    if isinstance(target, ReviewSession):
        db = object_session(target)
        review_session = target
    else:
        db = target
        review_session = db.get(ReviewSession, session_id)
    db.refresh(review_session)
    if not lifecycle.is_draft(review_session):
        return
    report = lifecycle.build_readiness_report(
        validation.validate_session_setup(db, review_session)
    )
    if not report.can_activate:
        return
    lifecycle.mark_validated(
        db,
        review_session=review_session,
        user=review_session.created_by_user,
        report=report,
    )
    db.commit()
