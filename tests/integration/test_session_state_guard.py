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


def _lands_at_the_lock(monkeypatch, db: Session, statement, *, at: int = 1) -> None:
    """Execute ``statement`` (another request's committed write) just as
    the ``at``-th lock is taken (the first by default), behind the ORM's
    back."""
    real = session_guard.lock_session
    taken: list[bool] = []

    def landing(db_, session_):
        taken.append(True)
        if len(taken) == at:
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


def _reviewer_emails(db: Session, session: ReviewSession) -> list[str]:
    from app.db.models import Reviewer

    db.expire_all()
    return sorted(
        db.execute(
            select(Reviewer.email).where(Reviewer.session_id == session.id)
        ).scalars()
    )


def test_a_roster_import_refuses_a_session_activated_at_the_lock(
    client, db: Session, monkeypatch
) -> None:
    """The route's own gate read ``validated``; the scheduled activation
    commits as the save starts. The import is refused with the 409, the
    roster is untouched, and ``ready`` is not written back to ``draft``."""
    client.post(
        "/operator/sessions",
        data={"name": "Import", "code": "guard-import"},
        follow_redirects=False,
    )
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "guard-import")
    ).scalar_one()
    session.status = "validated"
    db.commit()
    before = _reviewer_emails(db, session)
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "ready"))

    response = client.post(
        f"/operator/sessions/{session.id}/reviewers/import",
        data={"confirm_replace": "true", "acknowledge_response_loss": "true"},
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nZed,zed@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 409
    assert _reviewer_emails(db, session) == before
    assert db.get(ReviewSession, session.id).status == "ready"


def test_a_labelled_import_commits_nothing_before_a_later_gate_refuses(
    db: Session, monkeypatch
) -> None:
    """Codex on #2882: the label reconcile re-gates after the roster
    replace. The import is one commit, so a session archived between
    the two gates refuses with nothing committed, not after the replace."""
    from app.services import csv_imports

    user = User(email="op-labels@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    session = ReviewSession(
        name="Labels", code="guard-labels", created_by_user_id=user.id
    )
    db.add(session)
    db.commit()
    parsed = csv_imports.parse_reviewer_csv(
        b"ReviewerName,ReviewerEmail,ReviewerTag1.Tutor\n"
        b"Alice,alice@example.edu,senior\n"
    )
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "archived"), at=2)
    commits: list[bool] = []
    real_commit = db.commit
    monkeypatch.setattr(db, "commit", lambda: (commits.append(True), real_commit()))

    with pytest.raises(lifecycle.SessionStateConflict):
        csv_imports.save_reviewers(
            db,
            session=session,
            user=user,
            rows=parsed.rows,
            filename="reviewers.csv",
            correlation_id="t",
            field_labels_captured=parsed.field_labels,
        )

    assert commits == []


def test_a_row_edit_refuses_a_session_activated_at_the_lock(
    db: Session, monkeypatch
) -> None:
    from app.db.models import Reviewer
    from app.services import reviewers as reviewers_service

    session = _make_validated_session(db, "guard-row")
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == session.id)
    ).scalars().first()
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "ready"))

    with pytest.raises(lifecycle.SessionStateConflict):
        reviewers_service.update_reviewer(
            db, reviewer=reviewer, name="Renamed", user=_operator(db, session)
        )

    db.expire_all()
    assert db.get(Reviewer, reviewer.id).name != "Renamed"


def test_observers_keep_their_own_gate(db: Session, monkeypatch) -> None:
    """Observers stay editable on a running session; only an archive
    that commits first refuses the write."""
    from app.services import observers as observers_service

    session = _make_validated_session(db, "guard-observers")
    session.status = "ready"
    db.commit()
    observer = observers_service.create_observer(
        db,
        review_session=session,
        email="obs@example.edu",
        user=_operator(db, session),
    )
    assert observer.id is not None

    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "archived"))
    with pytest.raises(lifecycle.SessionStateConflict) as raised:
        observers_service.create_observer(
            db,
            review_session=session,
            email="late@example.edu",
            user=_operator(db, session),
        )
    assert raised.value.code == "archived"
