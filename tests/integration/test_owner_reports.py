"""Report emails to a session's other owners (14C Item 4).

An owner's lifecycle action mails each *other* owner who turned
"Another owner changes a session's state" on, from the acting owner's
mailbox, once the action has committed; the outcome is audited and a
refusal never undoes the action (author's ruling, 2026-11-06).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, SessionOperator, User
from app.services import owner_reports
from cordware import graph

from ._invitation_states import _create_session


class _Fake:
    def __init__(self) -> None:
        self.sent: list[graph.MailMessage] = []

    def send_mail(self, message: graph.MailMessage) -> None:
        self.sent.append(message)


class _Refusing:
    def send_mail(self, message: graph.MailMessage) -> None:
        raise graph.GraphError("forbidden", 403)


@pytest.fixture
def mailer(monkeypatch: pytest.MonkeyPatch) -> _Fake:
    fake = _Fake()
    monkeypatch.setattr(graph, "mailer_for", lambda _request, settings=None: fake)
    return fake


def _co_owner(
    db: Session,
    rs: ReviewSession,
    email: str,
    *,
    wants: bool,
    key: str = "email_report_lifecycle",
) -> User:
    user = User(
        email=email,
        display_name=email.split("@")[0].title(),
        is_operator=True,
        preferences={key: True} if wants else {},
    )
    db.add(user)
    db.flush()
    db.add(SessionOperator(session_id=rs.id, user_id=user.id, role="owner"))
    db.commit()
    return user


def _events(db: Session, event_type: str) -> list[AuditEvent]:
    return list(db.execute(select(AuditEvent).where(AuditEvent.event_type == event_type)).scalars())


def _archive(client: TestClient, rs: ReviewSession) -> None:
    response = client.post(
        "/operator/sessions/bulk-archive", data={"session_ids": [rs.id]}, follow_redirects=False
    )
    assert response.status_code == 303


def test_an_owner_who_asked_is_told_of_another_owners_archive(
    client: TestClient, db: Session, mailer: _Fake
) -> None:
    rs = _create_session(client, db, "report-archive")
    bob = _co_owner(db, rs, "bob@example.edu", wants=True)
    _co_owner(db, rs, "carol@example.edu", wants=False)

    _archive(client, rs)

    [message] = mailer.sent
    assert message.to == bob.email
    assert "archived" in message.subject
    assert rs.code in message.subject
    assert str(datetime.now(UTC).year) in message.body  # when
    assert f"/operator/sessions/{rs.public_id}" in message.body
    [sent] = _events(db, "report.sent")
    assert sent.session_id == rs.id
    assert sent.detail is not None
    assert sent.detail["counts"] == {"recipients": 1}
    assert "bob@example.edu" not in str(sent.detail)


def test_the_actor_is_never_told_of_their_own_action(
    client: TestClient, db: Session, mailer: _Fake
) -> None:
    rs = _create_session(client, db, "report-self")
    alice = db.execute(
        select(User)
        .join(SessionOperator, SessionOperator.user_id == User.id)
        .where(SessionOperator.session_id == rs.id)
    ).scalar_one()
    alice.preferences = {"email_report_lifecycle": True}
    db.commit()

    _archive(client, rs)

    assert mailer.sent == []
    assert _events(db, "report.sent") == []


def test_a_deleted_sessions_owners_are_told_without_a_link(
    client: TestClient, db: Session, mailer: _Fake
) -> None:
    rs = _create_session(client, db, "report-delete")
    rs.display_timezone = "Asia/Singapore"
    bob = _co_owner(db, rs, "bob-del@example.edu", wants=True)

    response = client.post(
        "/operator/sessions/bulk-delete",
        data={"session_ids": [rs.id], "confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    [message] = mailer.sent
    assert message.to == bob.email
    assert "deleted" in message.subject
    assert "/operator/sessions/" not in message.body
    # The session's zone, kept with its owners (Codex on #3694).
    assert "GMT+8 Asia/Singapore" in message.body
    [sent] = _events(db, "report.sent")
    assert sent.session_id is None


def test_a_refused_report_is_recorded_and_the_action_stands(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(graph, "mailer_for", lambda _request, settings=None: _Refusing())
    rs = _create_session(client, db, "report-refused")
    _co_owner(db, rs, "bob-ref@example.edu", wants=True)

    _archive(client, rs)

    db.refresh(rs)
    assert rs.status == "archived"
    [failed] = _events(db, "report.send_failed")
    assert failed.detail is not None
    assert failed.detail["reason"] == "forbidden"
    assert _events(db, "report.sent") == []


def _alice(db: Session, rs: ReviewSession) -> User:
    """The session's creator, its first owner."""
    user = (
        db.execute(
            select(User)
            .join(SessionOperator, SessionOperator.user_id == User.id)
            .where(SessionOperator.session_id == rs.id)
            .order_by(SessionOperator.id)
        )
        .scalars()
        .first()
    )
    assert user is not None
    return user


def test_a_rolled_back_action_reports_nothing(client: TestClient, db: Session) -> None:
    """A note waits for its transaction: a rollback drops it."""
    rs = _create_session(client, db, "report-rollback")
    _co_owner(db, rs, "bob-rb@example.edu", wants=True)
    owner_reports.note(
        db, event_type="session.archived", actor_user_id=_alice(db, rs).id, review_session=rs
    )
    assert db.info.get("owner_reports_pending"), "premise: the note was queued"
    db.rollback()
    db.commit()
    assert owner_reports.take_ready(db) == []


def test_a_savepoint_neither_promotes_nor_drops_a_note(client: TestClient, db: Session) -> None:
    """Cold read: a savepoint's release fires ``after_commit`` and its
    rollback ``after_soft_rollback`` (the session lock opens one on
    Postgres); only the outermost commit promotes, and a savepoint
    rollback leaves the outer notes standing."""
    rs = _create_session(client, db, "report-savepoint")
    _co_owner(db, rs, "bob-sp@example.edu", wants=True)
    owner_reports.note(
        db, event_type="session.archived", actor_user_id=_alice(db, rs).id, review_session=rs
    )
    db.begin_nested().commit()
    assert owner_reports.take_ready(db) == [], "a savepoint release promoted the note"
    db.begin_nested().rollback()
    assert db.info.get("owner_reports_pending"), "a savepoint rollback dropped the note"
    db.commit()
    [report] = owner_reports.take_ready(db)
    assert report.to == "bob-sp@example.edu"


def test_an_action_by_someone_not_an_owner_reports_nothing(client: TestClient, db: Session) -> None:
    """Group B is an owner's action: a participant's (a reviewer's Clear
    all, once reported) is never mailed from their mailbox."""
    rs = _create_session(client, db, "report-stranger")
    _co_owner(db, rs, "bob-st@example.edu", wants=True, key="email_report_destructive")
    stranger = User(email="reviewer@example.edu", display_name="Rev")
    db.add(stranger)
    db.flush()
    owner_reports.note(
        db, event_type="responses.deleted_all", actor_user_id=stranger.id, review_session=rs
    )
    assert not db.info.get("owner_reports_pending")
    assert "responses.cleared" not in owner_reports.REPORTED


def test_no_token_records_a_failure_and_the_action_stands(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_token(_request: object, settings: object = None) -> graph.Mailer:
        raise graph.GraphError("no_token")

    monkeypatch.setattr(graph, "mailer_for", no_token)
    rs = _create_session(client, db, "report-notoken")
    _co_owner(db, rs, "bob-nt@example.edu", wants=True)

    _archive(client, rs)

    db.refresh(rs)
    assert rs.status == "archived"
    [failed] = _events(db, "report.send_failed")
    assert failed.detail is not None
    assert failed.detail["reason"] == "no_token"


def test_a_roster_deleted_by_another_owner_is_reported(
    client: TestClient, db: Session, mailer: _Fake
) -> None:
    """The destructive row: the Reviewers roster deleted."""
    rs = _create_session(client, db, "report-roster")
    bob = _co_owner(db, rs, "bob-roster@example.edu", wants=True, key="email_report_destructive")
    _co_owner(db, rs, "carol-roster@example.edu", wants=True)  # lifecycle only

    response = client.post(
        f"/operator/sessions/{rs.public_id}/reviewers/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    [message] = mailer.sent
    assert message.to == bob.email
    assert "deleted the Reviewers roster of" in message.subject


def test_a_removed_owner_is_told_they_were_removed(
    client: TestClient, db: Session, mailer: _Fake
) -> None:
    """The owners row: the owner removed is told, since it concerns them."""
    rs = _create_session(client, db, "report-owner")
    bob = _co_owner(db, rs, "bob-owner@example.edu", wants=True, key="email_report_owners")

    response = client.post(
        f"/operator/sessions/{rs.public_id}/owners/{bob.id}/remove", follow_redirects=False
    )
    assert response.status_code == 303

    [message] = mailer.sent
    assert message.to == bob.email
    assert "removed Bob-Owner as an owner of" in message.subject


def test_a_row_turned_off_hears_nothing(client: TestClient, db: Session, mailer: _Fake) -> None:
    rs = _create_session(client, db, "report-off")
    _co_owner(db, rs, "bob-off@example.edu", wants=True, key="email_report_owners")

    _archive(client, rs)

    assert mailer.sent == []
