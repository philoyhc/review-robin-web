"""Test scaffolding for structure written onto a session past draft.

The service layer refuses instrument and visibility writes unless the
session is editable (findings Bc4, ``guide/segment_19U_post_assessment_7oct.md``
Item 1), as the routes always did. Some tests build a live or closed
session first and add a page break, a short label or a visibility cell
afterwards, as setup rather than as the behavior under test. This
wraps such a write: it reads as draft for the call, then the status the
test set is restored.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from app.services import session_lifecycle as lifecycle


@contextmanager
def past_draft_setup(db: Session, owner: object) -> Iterator[None]:
    """``owner`` is the session, or a row with a ``session`` attribute."""
    session = owner if isinstance(owner, ReviewSession) else owner.session
    if lifecycle.is_editable(session):
        yield
        return
    prior = session.status
    session.status = lifecycle.SessionStatus.draft.value
    db.commit()
    try:
        yield
    finally:
        session.status = prior
        db.commit()
