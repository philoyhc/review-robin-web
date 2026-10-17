"""Findings L3: the reviewer's Save, Submit, Clear and Recall are
decided under the session-row lock, in the service.

SQLite has one writer, so the race itself can't be run here. Each test
stands a spy in for ``session_guard.lock_session`` that, just before the
lock is taken, writes what the racer that won would have committed (a
Close, or a deadline now past) in the same transaction, and checks the
write is refused from what the lock re-read, leaving the saved answers
as they were.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import Response, ReviewSession
from app.schemas.responses import ResponseUpsert
from app.services import responses as responses_service
from app.services import session_guard
from app.services.session_guard import SessionStateConflict

from .test_responses_service import _seed


def _action(name: str, assignment_id: int):
    upserts = [
        ResponseUpsert(assignment_id=assignment_id, field_key="rating", value="2")
    ]
    if name == "save":
        return lambda db, **kw: responses_service.save_draft(
            db, upserts=upserts, **kw
        )
    if name == "submit":
        return lambda db, **kw: responses_service.submit(
            db, upserts=upserts, **kw
        )
    if name == "clear":
        return responses_service.clear_all
    return responses_service.recall


_PAST = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


@pytest.mark.parametrize(
    "racer", [{"status": "expired"}, {"deadline": _PAST}], ids=["close", "deadline"]
)
@pytest.mark.parametrize("name", ["save", "submit", "clear", "recall"])
def test_a_close_committed_before_the_lock_refuses_the_write(
    db: Session, monkeypatch: pytest.MonkeyPatch, name: str, racer: dict
) -> None:
    op, reviewer, review_session, assignment = _seed(db)
    stamped = dt.datetime(2026, 5, 9, tzinfo=dt.timezone.utc)
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=next(
                f.id
                for f in assignment.instrument.response_fields
                if f.field_key == "rating"
            ),
            value="5",
            saved_at=stamped,
            submitted_at=stamped,
        )
    )
    db.commit()
    assert review_session.status == "ready"

    real_lock = session_guard.lock_session
    calls: list[tuple[int, bool]] = []

    def closing_lock(
        db_: Session, session: ReviewSession, *, shared: bool = False
    ) -> ReviewSession:
        calls.append((session.id, shared))
        db_.execute(
            update(ReviewSession)
            .where(ReviewSession.id == session.id)
            .values(**racer)
        )
        return real_lock(db_, session, shared=shared)

    monkeypatch.setattr(session_guard, "lock_session", closing_lock)

    with pytest.raises(SessionStateConflict):
        _action(name, assignment.id)(
            db,
            review_session=review_session,
            reviewer=reviewer,
            user=op,
            correlation_id="corr",
        )
    db.rollback()

    # Shared, so reviewers writing at once don't queue behind each other.
    assert calls == [(review_session.id, True)]
    rows = list(
        db.execute(
            select(Response).where(Response.assignment_id == assignment.id)
        ).scalars()
    )
    assert [(r.value, r.submitted_at is not None) for r in rows] == [
        ("5", True)
    ]
