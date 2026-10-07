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


def _lands_at_the_lock(
    monkeypatch, db: Session, statement, *, at: int = 1, commit: bool = False
) -> None:
    """Execute ``statement`` (another request's committed write) just as
    the ``at``-th lock is taken (the first by default), behind the ORM's
    back. ``commit`` commits it, for a service that rolls back on refusal
    and would otherwise take the stand-in's write with it."""
    real = session_guard.lock_session
    taken: list[bool] = []

    def landing(db_, session_):
        taken.append(True)
        if len(taken) == at:
            db.execute(statement.execution_options(synchronize_session=False))
            if commit:
                db.commit()
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
    _lands_at_the_lock(
        monkeypatch, db, _status_becomes(session, "ready"), commit=True
    )

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


_LABELLED_IMPORTS = {
    "reviewers": (
        "parse_reviewer_csv",
        "save_reviewers",
        b"ReviewerName,ReviewerEmail,ReviewerTag1.Tutor\n"
        b"Alice,alice@example.edu,senior\n",
    ),
    "reviewees": (
        "parse_reviewee_csv",
        "save_reviewees",
        b"RevieweeName,RevieweeEmail,RevieweeTag1.Cohort\n"
        b"Carol,carol@example.edu,2026\n",
    ),
}


def _counting_commits(monkeypatch, db: Session) -> list[bool]:
    commits: list[bool] = []
    real_commit = db.commit
    monkeypatch.setattr(db, "commit", lambda: (commits.append(True), real_commit()))
    return commits


def _labels_session(db: Session) -> tuple[User, ReviewSession]:
    """A draft session that already overrides the reviewer and reviewee
    tag_2 labels, so an import's ``clear`` of tag_2 has a row to delete
    and reaches its own commit."""
    from app.db.models import SessionFieldLabel

    user = User(email="op-labels@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    session = ReviewSession(
        name="Labels", code="guard-labels", created_by_user_id=user.id
    )
    db.add(session)
    db.flush()
    for source_type in ("reviewer", "reviewee"):
        db.add(
            SessionFieldLabel(
                session_id=session.id,
                source_type=source_type,
                source_field="tag_2",
                label="Old",
            )
        )
    db.commit()
    return user, session


@pytest.mark.parametrize("roster", sorted(_LABELLED_IMPORTS))
# Lock 1 is the save's gate, 2 the label reconcile's, 3 the tag_1
# upsert's, 4 the tag_2 clear's (which deletes the seeded label), 5 the
# tag_3 clear's.
@pytest.mark.parametrize("at", [2, 5])
def test_a_labelled_import_commits_nothing_before_a_later_gate_refuses(
    db: Session, monkeypatch, roster: str, at: int
) -> None:
    """Codex on #2882: the label reconcile re-gates after the roster
    replace. The import is one commit, so a session archived at any later
    gate refuses with nothing committed — past an upsert and a clear at
    lock 5 — and the service drops the flushed half-import itself."""
    from app.db.models import Reviewee, Reviewer
    from app.services import csv_imports

    parse, save, body = _LABELLED_IMPORTS[roster]
    model = Reviewer if roster == "reviewers" else Reviewee
    user, session = _labels_session(db)
    parsed = getattr(csv_imports, parse)(body)
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "archived"), at=at)
    commits = _counting_commits(monkeypatch, db)

    with pytest.raises(lifecycle.SessionStateConflict):
        getattr(csv_imports, save)(
            db,
            session=session,
            user=user,
            rows=parsed.rows,
            filename=f"{roster}.csv",
            correlation_id="t",
            field_labels_captured=parsed.field_labels,
        )

    assert commits == []
    assert db.execute(
        select(model.id).where(model.session_id == session.id)
    ).all() == []


def test_a_relationship_import_commits_nothing_before_its_label_gate_refuses(
    db: Session, monkeypatch
) -> None:
    """Codex on #2882, the relationship import's half: the replace and
    the pair-context label reconcile are one commit, so the reconcile's
    gate (the import's second lock, after its entry gate) refuses with nothing
    committed and no relationship row left behind."""
    from app.db.models import Relationship, Reviewee, Reviewer
    from app.services import relationships

    user, session = _labels_session(db)
    reviewer = Reviewer(session_id=session.id, name="Alice", email="alice@example.edu")
    reviewee = Reviewee(
        session_id=session.id, name="Carol", email_or_identifier="carol@example.edu"
    )
    db.add_all([reviewer, reviewee])
    db.commit()
    parsed = relationships.parse_relationship_csv(
        b"ReviewerEmail,RevieweeEmail,PairContextTag1.Mentor of\n"
        b"alice@example.edu,carol@example.edu,cohort-a\n",
        reviewers=[reviewer],
        reviewees=[reviewee],
    )
    assert not parsed.is_blocked, parsed.issues
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "archived"), at=2)
    commits = _counting_commits(monkeypatch, db)

    with pytest.raises(lifecycle.SessionStateConflict):
        relationships.save_relationships(
            db,
            session=session,
            user=user,
            rows=parsed.rows,
            filename="relationships.csv",
            correlation_id="t",
            field_labels_captured=parsed.field_labels,
        )

    assert commits == []
    assert db.execute(
        select(Relationship.id).where(Relationship.session_id == session.id)
    ).all() == []


def test_a_refused_import_leaves_a_validated_session_validated(
    db: Session, monkeypatch
) -> None:
    """The flip goes with the edit: a validated session whose import is
    refused at a later gate stays validated, with no ``session.invalidated``
    row, rather than being demoted for an edit that never landed."""
    from app.services import csv_imports

    user, session = _labels_session(db)
    session.status = "validated"
    db.commit()
    parsed = csv_imports.parse_reviewer_csv(_LABELLED_IMPORTS["reviewers"][2])
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "archived"), at=2)

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

    db.expire_all()
    assert db.get(ReviewSession, session.id).status == "validated"
    assert _count(db, session, "session.invalidated") == 0


def test_a_refused_edit_does_not_demote_a_validated_session(db: Session) -> None:
    """The flip goes with the edit outside any single commit too: adding a
    display field the instrument already has refuses after the flip, and
    with nothing committed the session stays validated (before, the flip
    had committed on its own)."""
    from app.services import instruments
    from app.services.instruments import DisplaySourceError

    user, session = _labels_session(db)
    instrument = instruments.create_instrument(db, review_session=session, actor=user)
    existing = instrument.display_fields[0]
    session.status = "validated"
    db.commit()

    with pytest.raises(DisplaySourceError):
        instruments.add_display_field(
            db,
            instrument=instrument,
            source_type=existing.source_type,
            source_field=existing.source_field,
            label="Again",
            visible=True,
            actor=user,
        )
    # The flip did run before the refusal, so the test exercises it.
    assert session.status == "draft"
    db.rollback()  # the route redirects without committing

    assert db.get(ReviewSession, session.id).status == "validated"
    assert _count(db, session, "session.invalidated") == 0


def test_the_label_editor_commits_nothing_before_a_later_slot_refuses(
    db: Session, monkeypatch
) -> None:
    """Codex on #2882: the label form writes up to three slots, each
    re-gating. It is one commit, so a session archived at the second
    slot's gate refuses with the first slot's label not committed."""
    from app.db.models import SessionFieldLabel
    from app.web.routes_operator._shared import _save_field_labels

    user, session = _labels_session(db)
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "archived"), at=2)
    commits = _counting_commits(monkeypatch, db)

    with pytest.raises(lifecycle.SessionStateConflict):
        _save_field_labels(
            db,
            review_session=session,
            user=user,
            source_type="reviewer",
            slots=(("a", "tag_1"), ("b", "tag_2"), ("c", "tag_3")),
            submitted={"a": "Tutor", "b": "Year", "c": "Group"},
            correlation_id="t",
        )

    assert commits == []
    assert db.execute(
        select(SessionFieldLabel.id).where(
            SessionFieldLabel.session_id == session.id,
            SessionFieldLabel.source_field == "tag_1",
        )
    ).all() == []


def test_the_validated_to_draft_flip_lands_with_the_edit(
    db: Session, monkeypatch
) -> None:
    """Codex on #2882: the flip committed on its own released the lock
    the edit's gate took, so an archive (or a re-validate) could land
    between the flip and the edit. It now lands in the edit's one commit."""
    from app.services import reviewers

    user, session = _labels_session(db)
    session.status = "validated"
    db.commit()
    commits = _counting_commits(monkeypatch, db)

    reviewers.create_reviewer(
        db, review_session=session, name="Zed", email="zed@example.edu", user=user
    )

    assert commits == [True]
    assert db.get(ReviewSession, session.id).status == "draft"
    assert _count(db, session, "session.invalidated") == 1


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


# --------------------------------------------------------------------------- #
# Rung 4 — relationships and assignments                                      #
# --------------------------------------------------------------------------- #


def test_a_relationship_write_refuses_a_session_activated_at_the_lock(
    db: Session, monkeypatch
) -> None:
    from app.db.models import Relationship, Reviewee, Reviewer
    from app.services import relationships as relationships_service

    session = _make_validated_session(db, "guard-rel")
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == session.id)
    ).scalars().first()
    reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == session.id)
    ).scalars().first()
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "ready"))

    with pytest.raises(lifecycle.SessionStateConflict):
        relationships_service.create_relationship(
            db,
            review_session=session,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            user=_operator(db, session),
        )

    db.expire_all()
    assert not db.execute(
        select(Relationship.id).where(Relationship.session_id == session.id)
    ).all()


def _rung4_writes():
    from app.services import assignments, relationships as rel

    def _rel(db, session):
        from app.db.models import Relationship, Reviewee, Reviewer

        reviewer = db.execute(
            select(Reviewer).where(Reviewer.session_id == session.id)
        ).scalars().first()
        reviewee = db.execute(
            select(Reviewee).where(Reviewee.session_id == session.id)
        ).scalars().first()
        row = Relationship(
            session_id=session.id, reviewer_id=reviewer.id, reviewee_id=reviewee.id
        )
        db.add(row)
        db.flush()
        return row

    ids = dict(relationship_ids=[], correlation_id="t")
    return {
        "delete_all_relationships": lambda db, s, u: rel.delete_all_relationships(
            db, review_session=s, user=u, correlation_id="t"
        ),
        "update_relationship": lambda db, s, u: rel.update_relationship(
            db, relationship=_rel(db, s), tag_1="x", user=u, correlation_id="t"
        ),
        "bulk_inactivate": lambda db, s, u: rel.bulk_inactivate(
            db, review_session=s, user=u, **ids
        ),
        "bulk_reactivate": lambda db, s, u: rel.bulk_reactivate(
            db, review_session=s, user=u, **ids
        ),
        "delete_selected": lambda db, s, u: rel.delete_selected(
            db, review_session=s, user=u, **ids
        ),
        "set_instrument_self_reviews_active": (
            lambda db, s, u: assignments.set_instrument_self_reviews_active(
                db,
                review_session=s,
                instrument_id=s.instruments[0].id,
                user=u,
                active=False,
                correlation_id="t",
            )
        ),
        "bulk_set_assignment_include": (
            lambda db, s, u: assignments.bulk_set_assignment_include(
                db,
                review_session=s,
                assignment_ids=[],
                include=False,
                user=u,
                correlation_id="t",
            )
        ),
    }


@pytest.mark.parametrize("write", sorted(_rung4_writes()))
def test_each_rung4_write_refuses_a_session_activated_at_the_lock(
    db: Session, monkeypatch, write: str
) -> None:
    """Every relationship and assignment write gates first: a session the
    scheduler activated as the write starts is refused, and stays ready."""
    session = _make_validated_session(db, f"guard-{write[:20]}")
    user = _operator(db, session)
    _lands_at_the_lock(
        monkeypatch, db, _status_becomes(session, "ready"), commit=True
    )

    with pytest.raises(lifecycle.SessionStateConflict):
        _rung4_writes()[write](db, session, user)

    db.expire_all()
    assert db.get(ReviewSession, session.id).status == "ready"


def test_a_relationship_import_refuses_at_its_entry_gate(db: Session) -> None:
    """Without the entry gate the import would flip the validated session
    it loaded to draft, and that flip would be flushed over the committed
    ready before the label gate re-read it."""
    from app.db.models import Reviewee, Reviewer
    from app.services import relationships

    session = _make_validated_session(db, "guard-rel-entry")
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == session.id)
    ).scalars().first()
    reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == session.id)
    ).scalars().first()
    parsed = relationships.parse_relationship_csv(
        f"ReviewerEmail,RevieweeEmail\n{reviewer.email},{reviewee.email_or_identifier}\n".encode(),
        reviewers=[reviewer],
        reviewees=[reviewee],
    )
    assert not parsed.is_blocked, parsed.issues
    # The scheduler commits ``ready`` while the request still holds the
    # ``validated`` row it loaded.
    db.execute(
        _status_becomes(session, "ready").execution_options(
            synchronize_session=False
        )
    )
    db.commit()
    assert session.status == "validated"

    with pytest.raises(lifecycle.SessionStateConflict):
        relationships.save_relationships(
            db,
            session=session,
            user=_operator(db, session),
            rows=parsed.rows,
            filename="relationships.csv",
            correlation_id="t",
            field_labels_captured=parsed.field_labels,
        )

    db.expire_all()
    assert db.get(ReviewSession, session.id).status == "ready"


def test_generate_is_one_commit_from_its_gate(db: Session, monkeypatch) -> None:
    """Generate's display-field seed (and its drift correction) committed
    on their own after the main commit, once the gate's lock was gone. The
    seed is forced to write here; the whole Generate is still one commit."""
    from app.db.models import Assignment
    from app.services import assignments
    import app.services.instruments as instruments_pkg

    session = _make_validated_session(db, "guard-generate-once")
    monkeypatch.setattr(
        instruments_pkg, "seed_display_fields_from_assignments", lambda db_, s_: 1
    )
    commits = _counting_commits(monkeypatch, db)

    assignments.replace_assignments(
        db, review_session=session, user=_operator(db, session), correlation_id="t"
    )

    assert commits == [True]
    assert db.execute(
        select(Assignment.id).where(Assignment.session_id == session.id)
    ).all()


def test_generate_refuses_a_session_activated_at_the_lock(
    db: Session, monkeypatch
) -> None:
    """Generate on a session the scheduler activated mid-request would
    replace the live assignments; it is refused instead."""
    from app.db.models import Assignment
    from app.services import assignments

    session = _make_validated_session(db, "guard-generate")
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "ready"))

    with pytest.raises(lifecycle.SessionStateConflict):
        assignments.replace_assignments(
            db,
            review_session=session,
            user=_operator(db, session),
            correlation_id="t",
        )

    db.expire_all()
    assert not db.execute(
        select(Assignment.id).where(Assignment.session_id == session.id)
    ).all()


# --------------------------------------------------------------------------- #
# Rung 5 — instruments                                                        #
# --------------------------------------------------------------------------- #


def test_an_instrument_edit_refuses_a_session_activated_at_the_lock(
    db: Session, monkeypatch
) -> None:
    from app.services import instruments as instruments_service

    session = _make_validated_session(db, "guard-instrument")
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalars().first()
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "ready"))

    with pytest.raises(lifecycle.SessionStateConflict):
        instruments_service.update_short_label(
            db,
            instrument=instrument,
            short_label="Late",
            actor=_operator(db, session),
        )

    db.expire_all()
    assert db.get(Instrument, instrument.id).short_label != "Late"


def test_an_async_instrument_route_answers_409_off_the_event_loop(
    client, db: Session, monkeypatch
) -> None:
    """The identity JSON route reads its body, then runs the guarded
    write in the threadpool: the conflict still reaches the operator as
    the 409."""
    client.post(
        "/operator/sessions",
        data={"name": "Identity", "code": "guard-identity"},
        follow_redirects=False,
    )
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "guard-identity")
    ).scalar_one()
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalars().first()
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "ready"))

    response = client.post(
        f"/operator/sessions/{session.id}/instruments/{instrument.id}/identity",
        json={"short_label": "Late"},
    )

    assert response.status_code == 409
    db.expire_all()
    assert db.get(Instrument, instrument.id).short_label != "Late"


def test_an_identity_save_of_both_fields_is_one_commit(
    client, db: Session, monkeypatch
) -> None:
    """Short label and description each gate and used to commit apart, so
    a session archived at the description's gate refused after the label
    had landed. The route is one unit: the 409 lands neither."""
    client.post(
        "/operator/sessions",
        data={"name": "Identity", "code": "guard-identity-two"},
        follow_redirects=False,
    )
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "guard-identity-two")
    ).scalar_one()
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalars().first()
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "archived"), at=2)
    commits = _counting_commits(monkeypatch, db)

    response = client.post(
        f"/operator/sessions/{session.id}/instruments/{instrument.id}/identity",
        json={"short_label": "Late", "description": "Also late"},
    )

    assert response.status_code == 409
    assert commits == []
    db.expire_all()
    assert db.get(Instrument, instrument.id).short_label != "Late"


def _rung5_writes():
    from app.services import instruments as i
    from app.services import visibility_policies as vp

    def first(rows):
        return rows[0] if rows else None

    def df(inst):
        return first(list(inst.display_fields))

    def rf(inst):
        return first(list(inst.response_fields))

    return {
        "set_band1_assignment_rules": lambda db, s, n, u: i.set_band1_assignment_rules(
            db, instrument=n, link1_mode=None, link1_combinator=None,
            link1_rules=[], link2_mode=None, link2_combinator=None,
            link2_rules=[], actor=u,
        ),
        "set_exclude_self_reviews": lambda db, s, n, u: i.set_exclude_self_reviews(
            db, instrument=n, value=True, actor=u
        ),
        "set_band2_state": lambda db, s, n, u: i.set_band2_state(
            db, instrument=n, state={}, actor=u
        ),
        "add_display_field": lambda db, s, n, u: i.add_display_field(
            db, instrument=n, source_type="reviewee", source_field="tag_1",
            label="", visible=True, actor=u,
        ),
        "update_display_field": lambda db, s, n, u: i.update_display_field(
            db, field=df(n), label="x", visible=True, actor=u
        ),
        "delete_display_field": lambda db, s, n, u: i.delete_display_field(
            db, field=df(n), actor=u
        ),
        "move_display_field": lambda db, s, n, u: i.move_display_field(
            db, field=df(n), direction="down", actor=u
        ),
        "reorder_display_fields": lambda db, s, n, u: i.reorder_display_fields(
            db, instrument=n, ordered_ids=[], actor=u
        ),
        "set_sort_display_fields": lambda db, s, n, u: i.set_sort_display_fields(
            db, instrument=n, fields=[], actor=u
        ),
        "create_instrument": lambda db, s, n, u: i.create_instrument(
            db, review_session=s, actor=u
        ),
        "replicate_instrument": lambda db, s, n, u: i.replicate_instrument(
            db, review_session=s, source=n, actor=u
        ),
        "delete_instrument": lambda db, s, n, u: i.delete_instrument(
            db, instrument=n, actor=u
        ),
        "update_instrument_description": (
            lambda db, s, n, u: i.update_instrument_description(
                db, instrument=n, description="x", actor=u
            )
        ),
        "set_group_boundary": lambda db, s, n, u: i.set_group_boundary(
            db, instrument=n, boundary_pairs=[], actor=u
        ),
        "set_unit_of_review": lambda db, s, n, u: i.set_unit_of_review(
            db, instrument=n, mode="reviewee", boundary_pairs=[], actor=u
        ),
        "set_column_widths": lambda db, s, n, u: i.set_column_widths(
            db, instrument=n, widths={}, actor=u
        ),
        "reorder_instruments": lambda db, s, n, u: i.reorder_instruments(
            db, review_session=s, items=[]
        ),
        "create_page_break_after": lambda db, s, n, u: i.create_page_break_after(
            db, instrument=n
        ),
        "clear_page_break": lambda db, s, n, u: i.clear_page_break(db, instrument=n),
        "bulk_save_fields": lambda db, s, n, u: i.bulk_save_fields(
            db, instrument=n, rows=[], actor=u
        ),
        "add_response_field": lambda db, s, n, u: i.add_response_field(
            db, instrument=n, field_key="late", label="Late",
            response_type="text", required=False, help_text="",
            help_text_visible=False, actor=u,
        ),
        "add_default_response_field": lambda db, s, n, u: i.add_default_response_field(
            db, instrument=n, actor=u
        ),
        "update_response_field": lambda db, s, n, u: i.update_response_field(
            db, field=rf(n), label="x", required=False, validation=None,
            help_text="", help_text_visible=False, actor=u,
        ),
        "delete_response_field": lambda db, s, n, u: i.delete_response_field(
            db, field=rf(n), confirm=True, actor=u
        ),
        "move_response_field": lambda db, s, n, u: i.move_response_field(
            db, field=rf(n), direction="down", actor=u
        ),
        "upsert_policy": lambda db, s, n, u: vp.upsert_policy(
            db, review_session=s, instrument=n, audience="reviewer",
            while_ongoing_mode=None, after_release_mode=None, user=u,
        ),
        "upsert_many": lambda db, s, n, u: vp.upsert_many(
            db, review_session=s, instrument=n, rows=[], user=u
        ),
    }



@pytest.mark.parametrize("write", sorted(_rung5_writes()))
def test_each_rung5_write_refuses_a_session_activated_at_the_lock(
    db: Session, monkeypatch, write: str
) -> None:
    """Every instrument and visibility writer gates first: a session the
    scheduler activated as the write starts is refused, and stays ready."""
    session = _make_validated_session(db, f"g5-{write[:24]}")
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalars().first()
    user = _operator(db, session)
    _lands_at_the_lock(
        monkeypatch, db, _status_becomes(session, "ready"), commit=True
    )

    with pytest.raises(lifecycle.SessionStateConflict):
        _rung5_writes()[write](db, session, instrument, user)

    db.expire_all()
    assert db.get(ReviewSession, session.id).status == "ready"


def test_a_band2_save_is_one_commit(client, db: Session, monkeypatch) -> None:
    """The Band 2 save syncs display-field visibility one field at a time,
    and each sync committed, releasing the gate's lock before the rest of
    the save. The route is now one unit: a session archived at the second
    field's gate commits nothing."""
    from app.db.models import InstrumentDisplayField
    from app.services import instruments as instruments_service

    client.post(
        "/operator/sessions",
        data={"name": "Band two", "code": "guard-band2"},
        follow_redirects=False,
    )
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "guard-band2")
    ).scalar_one()
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalars().first()
    for field in ("tag_1", "tag_2"):
        instruments_service.add_display_field(
            db, instrument=instrument, source_type="reviewee",
            source_field=field, label="", visible=True,
            actor=_operator(db, session),
        )
    # Lock 1 is the save's gate, 2 and 3 the two fields' visibility syncs.
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "archived"), at=3)
    commits = _counting_commits(monkeypatch, db)

    response = client.post(
        f"/operator/sessions/{session.id}/instruments/{instrument.id}/band2-state",
        json={"selected_display_keys": []},
    )

    assert response.status_code == 409
    assert commits == []
    db.expire_all()
    assert all(
        f.visible
        for f in db.execute(
            select(InstrumentDisplayField).where(
                InstrumentDisplayField.instrument_id == instrument.id,
                InstrumentDisplayField.source_field.in_(["tag_1", "tag_2"]),
            )
        ).scalars()
    )


# --------------------------------------------------------------------------- #
# Rung 6 — the session saves                                                  #
# --------------------------------------------------------------------------- #


def test_update_session_refuses_a_session_activated_at_the_lock(
    db: Session, monkeypatch
) -> None:
    from app.services import sessions as sessions_service

    session = _make_validated_session(db, "guard-update")
    payload = sessions_service.edit_payload(
        session, name="Renamed", code=session.code, deadline=session.deadline
    )
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "ready"))

    with pytest.raises(lifecycle.SessionStateConflict):
        sessions_service.update_session(
            db,
            review_session=session,
            user=_operator(db, session),
            payload=payload,
        )

    db.expire_all()
    assert db.get(ReviewSession, session.id).name != "Renamed"


def test_delete_session_refuses_a_session_activated_at_the_lock(
    db: Session, monkeypatch
) -> None:
    from app.services import sessions as sessions_service

    session = _make_validated_session(db, "guard-delete")
    session_id = session.id
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "ready"))

    with pytest.raises(lifecycle.SessionStateConflict) as raised:
        sessions_service.delete_session(
            db, review_session=session, user=_operator(db, session)
        )

    assert raised.value.code == "session_ready"
    db.expire_all()
    assert db.get(ReviewSession, session_id) is not None


def test_the_lobby_bulk_delete_skips_a_session_activated_at_the_lock(
    client, db: Session, monkeypatch
) -> None:
    """One row of a bulk Delete activated since the request read it is
    skipped, as the route's own filter skips a ``ready`` row — not a 409
    for the whole selection."""
    client.post(
        "/operator/sessions",
        data={"name": "Bulk", "code": "guard-bulk"},
        follow_redirects=False,
    )
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "guard-bulk")
    ).scalar_one()
    session_id = session.id
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "ready"))

    response = client.post(
        "/operator/sessions/bulk-delete",
        data={"session_ids": [str(session_id)], "confirm": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    db.expire_all()
    assert db.get(ReviewSession, session_id) is not None


# --------------------------------------------------------------------------- #
# Acting on the cumulative read                                               #
# --------------------------------------------------------------------------- #


def test_purge_and_archive_decides_under_the_lock(
    db: Session, monkeypatch
) -> None:
    """A scheduled activation committing as Purge and archive starts: the
    session is not archivable on the re-read row, so nothing is purged."""
    from app.db.models import Reviewer
    from app.services import session_purge

    session = _make_validated_session(db, "guard-purge")
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "ready"))

    assert not session_purge.purge_and_archive(
        db,
        review_session=session,
        user=_operator(db, session),
        purge=["rosters", "responses"],
    )
    db.expire_all()
    assert db.get(ReviewSession, session.id).status == "ready"
    assert db.execute(
        select(Reviewer.id).where(Reviewer.session_id == session.id)
    ).all()


def test_a_quick_setup_slot_reports_the_lifecycle_reason(
    client, db: Session, monkeypatch
) -> None:
    """Refused under the lock, a Quick Setup roster slot answers with its
    own ``lifecycle`` reason, as its gate does, not the bare 409 page."""
    client.post(
        "/operator/sessions",
        data={"name": "QS", "code": "guard-qs"},
        follow_redirects=False,
    )
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "guard-qs")
    ).scalar_one()
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, "ready"))

    response = client.post(
        f"/operator/sessions/{session.id}/quick-setup/reviewers",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nZed,zed@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "quick_setup_reason=lifecycle" in response.headers["location"]
    assert _reviewer_emails(db, session) == []


@pytest.mark.parametrize("guarded", ["delete_responses", "apply_settings"])
def test_the_other_session_writes_refuse_at_the_lock(
    db: Session, monkeypatch, guarded
) -> None:
    from app.services import responses as responses_service
    from app.services import session_config_io

    session = _make_validated_session(db, f"guard-{guarded}")
    target = "ready"
    _lands_at_the_lock(monkeypatch, db, _status_becomes(session, target))

    with pytest.raises(lifecycle.SessionStateConflict):
        if guarded == "delete_responses":
            responses_service.delete_all_for_session(
                db,
                review_session=session,
                user=_operator(db, session),
                correlation_id="t",
            )
        else:
            session_config_io.apply_session_config(db, session, [])
