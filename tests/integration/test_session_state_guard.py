"""Findings Bc4 / segment 19U: a lifecycle-state gate is decided on the
session row re-read under the lock, in the service.

SQLite never blocks on ``FOR NO KEY UPDATE``, so each test stands in for
the racing request by committing its write at the moment the lock is
taken (``_lands_at_the_lock``). A service that reads the row as it was
loaded misses that write; one that re-reads under the lock sees it.
These tests prove the reads happen in that order, not that Postgres
blocks.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, ReviewSession, User
from app.services import session_guard
from app.services import session_lifecycle as lifecycle
from app.web.routes_operator._shared import _lifecycle_error_response

from .test_scheduled_activation import _make_validated_session


def _lands_at_the_lock(monkeypatch, db: Session, statement) -> None:
    """Execute ``statement`` (another request's committed write) just as
    the first lock is taken, behind the ORM's back."""
    real = session_guard.lock_session
    fired: list[bool] = []

    def landing(db_, session_):
        if not fired:
            fired.append(True)
            db.execute(statement.execution_options(synchronize_session=False))
        return real(db_, session_)

    monkeypatch.setattr(session_guard, "lock_session", landing)


def _status_becomes(session: ReviewSession, status: str):
    return (
        update(ReviewSession)
        .where(ReviewSession.id == session.id)
        .values(status=status)
    )


def _count(db: Session, session: ReviewSession, event_type: str) -> int:
    return len(
        db.execute(
            select(AuditEvent.id).where(
                AuditEvent.session_id == session.id,
                AuditEvent.event_type == event_type,
            )
        ).all()
    )


def _operator(db: Session, session: ReviewSession) -> User:
    return db.execute(select(User).order_by(User.id)).scalars().first()


def test_manual_activate_after_the_scheduled_one_refuses(
    db: Session, monkeypatch
) -> None:
    """The scheduled activation commits as the operator's Activate
    starts: the manual one re-reads ``ready`` and refuses, rather than
    activating a second time."""
    session = _make_validated_session(db, "guard-activate")
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "ready"))

    with pytest.raises(lifecycle.LifecycleError) as raised:
        lifecycle.activate_session(
            db,
            review_session=session,
            user=_operator(db, session),
            report=lifecycle.build_readiness_report([]),
            acknowledge_warnings=True,
        )

    assert raised.value.code == "not_validated"
    assert _count(db, session, "session.activated") == 0


def test_invalidate_reads_the_committed_status(
    db: Session, monkeypatch
) -> None:
    """A setup save's ``validated → draft`` flip, on a session activated
    since the request loaded it, leaves ``ready`` alone."""
    session = _make_validated_session(db, "guard-invalidate")
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "ready"))

    lifecycle.invalidate_if_validated(
        db,
        review_session=session,
        user=_operator(db, session),
        reason="test",
    )

    db.expire_all()
    assert db.get(ReviewSession, session.id).status == "ready"
    assert _count(db, session, "session.invalidated") == 0


def test_require_editable_refuses_on_the_committed_status(
    db: Session, monkeypatch
) -> None:
    session = _make_validated_session(db, "guard-editable")
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "ready"))

    with pytest.raises(lifecycle.SessionStateConflict) as raised:
        lifecycle.require_editable(db, session)

    assert raised.value.code == "not_editable"
    assert str(raised.value) == "Session is ready; revert to draft to edit"


def test_require_editable_passes_an_editable_session(db: Session) -> None:
    session = _make_validated_session(db, "guard-editable-ok")
    assert lifecycle.require_editable(db, session) is session


@pytest.mark.parametrize(
    ("guard", "status", "code"),
    [
        (lifecycle.require_not_archived, "archived", "archived"),
        (lifecycle.require_not_ready, "ready", "session_ready"),
    ],
)
def test_the_other_gates_refuse_their_state(
    db: Session, monkeypatch, guard, status, code
) -> None:
    session = _make_validated_session(db, f"guard-{code}")
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, status))

    with pytest.raises(lifecycle.SessionStateConflict) as raised:
        guard(db, session)

    assert raised.value.code == code


def test_a_state_conflict_answers_409() -> None:
    response = _lifecycle_error_response(
        lifecycle.SessionStateConflict("Session is ready", code="anything")
    )
    assert response.status_code == 409


def _open_instruments(db: Session, session: ReviewSession) -> None:
    db.execute(
        update(Instrument)
        .where(Instrument.session_id == session.id)
        .values(accepting_responses=True, deadline_closed_at=None)
    )
    db.commit()


def test_the_deadline_close_rereads_under_the_lock(
    db: Session, monkeypatch
) -> None:
    """Another request closed the instruments as this one starts: the
    close is not written, or audited, twice."""
    session = _make_validated_session(db, "guard-deadline")
    session.status = "ready"
    session.deadline = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    _open_instruments(db, session)
    _lands_at_the_lock(
        monkeypatch,
        db,
        update(Instrument)
        .where(Instrument.session_id == session.id)
        .values(
            accepting_responses=False,
            deadline_closed_at=datetime.now(timezone.utc),
        ),
    )

    assert lifecycle.observe_deadline(db, session) == 0
    assert _count(db, session, "instrument.closed") == 0


def test_the_live_reopen_rereads_the_status(
    db: Session, monkeypatch
) -> None:
    """A Close session committing as a reviewer's GET heals a closed
    instrument: the heal re-reads ``expired`` and leaves it closed."""
    session = _make_validated_session(db, "guard-reopen")
    session.status = "ready"
    session.deadline = datetime.now(timezone.utc) + timedelta(days=1)
    db.commit()
    db.execute(
        update(Instrument)
        .where(Instrument.session_id == session.id)
        .values(accepting_responses=False)
    )
    db.commit()
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "expired"))

    lifecycle.observe_deadline(db, session)

    db.expire_all()
    accepting = db.execute(
        select(Instrument.accepting_responses).where(
            Instrument.session_id == session.id
        )
    ).scalars().all()
    assert accepting and not any(accepting)
    assert _count(db, session, "instrument.opened") == 0
