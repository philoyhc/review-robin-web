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
from urllib.parse import parse_qs, urlsplit

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


def test_the_deadline_close_rereads_the_end_under_the_lock(
    db: Session, monkeypatch
) -> None:
    """End cleared by a save that commits as the GET starts: nothing is
    closed, and the re-read row (no deadline) is not dereferenced."""
    session = _make_validated_session(db, "guard-end-cleared")
    session.status = "ready"
    session.deadline = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    _open_instruments(db, session)
    _lands_at_the_lock(
        monkeypatch,
        db,
        update(ReviewSession)
        .where(ReviewSession.id == session.id)
        .values(deadline=None),
    )

    assert lifecycle.observe_deadline(db, session) == 0
    assert _count(db, session, "instrument.closed") == 0


def test_release_refuses_a_session_archived_at_the_lock(
    db: Session, monkeypatch
) -> None:
    session = _make_validated_session(db, "guard-release")
    session.status = "expired"
    db.commit()
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "archived"))

    with pytest.raises(lifecycle.SessionStateConflict) as raised:
        lifecycle.release_responses_now(
            db, review_session=session, user=_operator(db, session)
        )
    assert str(raised.value) == "Archived sessions can't have responses released."
    assert _count(db, session, "session.responses_released") == 0


def test_stop_release_refuses_a_session_archived_at_the_lock(
    db: Session, monkeypatch
) -> None:
    session = _make_validated_session(db, "guard-stop-release")
    session.status = "expired"
    db.commit()
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "archived"))

    with pytest.raises(lifecycle.SessionStateConflict) as raised:
        lifecycle.stop_responses_release(
            db, review_session=session, user=_operator(db, session)
        )
    assert str(raised.value) == "Archived sessions can't have releases stopped."


@pytest.mark.parametrize(
    ("path", "button", "message", "event"),
    [
        (
            "release-responses",
            "release_responses",
            "Archived sessions can't have responses released.",
            "session.responses_released",
        ),
        (
            "stop-release",
            "stop_release",
            "Archived sessions can't have releases stopped.",
            "session.responses_release_stopped",
        ),
    ],
)
def test_the_release_routes_answer_an_archive_race_as_their_own_gate(
    client, db: Session, monkeypatch, path, button, message, event
) -> None:
    client.post(
        "/operator/sessions",
        data={"name": "Release", "code": f"guard-{button}"},
        follow_redirects=False,
    )
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == f"guard-{button}")
    ).scalar_one()
    session.status = "expired"
    db.commit()
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "archived"))

    response = client.post(
        f"/operator/sessions/{session.id}/workflow/{path}",
        follow_redirects=False,
    )

    assert response.status_code == 303
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query["super_status"] == ["failed"]
    assert query["super_button"] == [button]
    assert query["super_step"] == ["precondition"]
    assert query["super_error"] == [message]
    assert _count(db, session, event) == 0


@pytest.mark.parametrize(
    ("start", "lands", "call", "code"),
    [
        ("draft", "ready", "mark_validated", "not_draft"),
        ("ready", "expired", "expire_session", "not_ready"),
        ("ready", "draft", "revert_session_to_draft", "not_ready"),
        ("draft", "archived", "archive_session", "already_archived"),
        ("archived", "draft", "unarchive_session", "not_archived"),
    ],
)
def test_each_transition_decides_under_the_lock(
    db: Session, monkeypatch, start, lands, call, code
) -> None:
    """Another request moved the session as this transition starts: it
    reads the committed status and refuses, rather than acting on the
    status it loaded."""
    session = _make_validated_session(db, f"guard-{call}")
    session.status = start
    db.commit()
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, lands))
    kwargs = {"review_session": session, "user": _operator(db, session)}
    if call == "mark_validated":
        kwargs["report"] = lifecycle.build_readiness_report([])
    if call == "revert_session_to_draft":
        kwargs["confirm"] = True

    with pytest.raises(lifecycle.LifecycleError) as raised:
        getattr(lifecycle, call)(db, **kwargs)

    assert raised.value.code == code


def test_operator_revert_decides_its_path_under_the_lock(
    db: Session, monkeypatch
) -> None:
    """The scheduled activation commits as Revert starts on a session the
    request loaded as ``validated``: the revert takes the ``ready`` path
    (which asks for the confirm) instead of writing ``draft`` over it."""
    session = _make_validated_session(db, "guard-operator-revert")
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "ready"))

    with pytest.raises(lifecycle.LifecycleError) as raised:
        lifecycle.operator_revert(
            db,
            review_session=session,
            user=_operator(db, session),
            confirm=False,
        )

    assert raised.value.code == "needs_confirm"
    assert _count(db, session, "session.invalidated") == 0


def test_a_double_submitted_bulk_unarchive_skips_the_row(
    client, db: Session, monkeypatch
) -> None:
    client.post(
        "/operator/sessions",
        data={"name": "Unarchive", "code": "guard-unarchive"},
        follow_redirects=False,
    )
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "guard-unarchive")
    ).scalar_one()
    session.status = "archived"
    db.commit()
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "draft"))

    response = client.post(
        "/operator/sessions/bulk-unarchive",
        data={"session_ids": [str(session.id)]},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert _count(db, session, "session.unarchived") == 0


def test_the_revert_route_decides_its_path_under_the_lock(
    client, db: Session, monkeypatch
) -> None:
    """Session Home's Revert goes through ``operator_revert``: a session
    activated as the request starts is answered on the ``ready`` path
    (the confirm is required) rather than invalidated."""
    client.post(
        "/operator/sessions",
        data={"name": "Revert", "code": "guard-revert-route"},
        follow_redirects=False,
    )
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "guard-revert-route")
    ).scalar_one()
    session.status = "validated"
    db.commit()
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "ready"))

    response = client.post(
        f"/operator/sessions/{session.id}/revert", follow_redirects=False
    )

    assert response.status_code == 400
    assert _count(db, session, "session.invalidated") == 0
