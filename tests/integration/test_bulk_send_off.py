"""14F rung 3a: per-row Send and Remind send now; bulk sends wait for 14G.

- `RRW_BULK_SEND` ships off. Off, the Workflow card's Send invites and
  Send reminders render disabled with a line pointing to the session link,
  and their routes refuse. The suite runs with it on (`tests/conftest.py`).
- Per-row Send and Remind dispatch the row they queue through the
  operator's mailer, with the operator's Email settings, and say how it
  went on Invitations.
- With no Microsoft token nothing is queued or rotated: the page says to
  reload.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.db.models import AuditEvent, EmailOutbox, Invitation, User
from cordware import graph
from cordware.graph import FakeMailer, GraphError, MailMessage

from .test_invitations import _ready_session


@pytest.fixture
def bulk_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "bulk_send", False)


def _invitation(db: Session, session_id: int) -> Invitation:
    return db.execute(select(Invitation).where(Invitation.session_id == session_id)).scalar_one()


def test_the_shipped_default_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RRW_BULK_SEND", raising=False)
    assert Settings(_env_file=None).bulk_send is False  # pyright: ignore[reportCallIssue]  -- a pydantic-settings init option


def test_off_the_bulk_buttons_are_disabled_and_say_why(
    client: TestClient, db: Session, bulk_off: None
) -> None:
    session = _ready_session(client, db, code="bulk-off-card")
    body = client.get(f"/operator/sessions/{session.public_id}/invitations").text
    button = body.split('form="next-action-send-invites-form"', 1)[1].split(">", 1)[0]
    assert "disabled" in button
    assert "data-bulk-off" in body
    assert "share the session link" in body


@pytest.mark.parametrize("action", ["send-all", "remind-incomplete"])
def test_off_the_bulk_routes_refuse(
    client: TestClient, db: Session, bulk_off: None, action: str
) -> None:
    session = _ready_session(client, db, code=f"bulk-off-{action[:6]}")
    response = client.post(
        f"/operator/sessions/{session.public_id}/invitations/{action}", follow_redirects=False
    )
    assert response.status_code == 409
    assert db.execute(select(func.count()).select_from(EmailOutbox)).scalar() == 0


def test_off_a_per_row_send_still_sends(
    client: TestClient, db: Session, bulk_off: None, fake_mailer: FakeMailer
) -> None:
    session = _ready_session(client, db, code="bulk-off-row")
    invitation = _invitation(db, session.id)
    response = client.post(
        f"/operator/sessions/{session.public_id}/invitations/{invitation.id}/send",
        follow_redirects=False,
    )
    assert response.headers["location"].endswith("/invitations?email=sent")
    [message] = fake_mailer.sent
    assert message.to == "rae@example.edu"
    page = client.get(response.headers["location"]).text
    assert "Sent from your mailbox." in page


def test_a_per_row_reminder_sends_too(
    client: TestClient, db: Session, fake_mailer: FakeMailer
) -> None:
    session = _ready_session(client, db, code="row-remind")
    invitation = _invitation(db, session.id)
    client.post(f"/operator/sessions/{session.public_id}/invitations/{invitation.id}/send")
    response = client.post(
        f"/operator/sessions/{session.public_id}/invitations/{invitation.id}/remind",
        follow_redirects=False,
    )
    assert response.headers["location"].endswith("/invitations?email=sent")
    assert len(fake_mailer.sent) == 2
    statuses = db.execute(select(EmailOutbox.status)).scalars().all()
    assert sorted(statuses) == ["sent", "sent"]


def test_no_token_queues_nothing_and_rotates_nothing(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _ready_session(client, db, code="row-no-token")
    invitation = _invitation(db, session.id)
    status_before = invitation.status

    def no_token(_request: object, settings: object = None) -> graph.Mailer:
        raise GraphError("no_token")

    monkeypatch.setattr(graph, "mailer_for", no_token)
    response = client.post(
        f"/operator/sessions/{session.public_id}/invitations/{invitation.id}/send",
        follow_redirects=False,
    )
    assert response.headers["location"].endswith("/invitations?email=failed&kind=no_token")
    assert db.execute(select(func.count()).select_from(EmailOutbox)).scalar() == 0
    db.refresh(invitation)
    assert invitation.status == status_before
    page = client.get(response.headers["location"]).text
    assert "The email was not sent." in page
    assert "Reload the page" in page


def test_a_refused_send_reads_failed_with_its_reason(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Refusing:
        def send_mail(self, message: MailMessage) -> None:
            raise GraphError("forbidden", 403)

    monkeypatch.setattr(graph, "mailer_for", lambda _request, settings=None: Refusing())
    session = _ready_session(client, db, code="row-refused")
    invitation = _invitation(db, session.id)
    response = client.post(
        f"/operator/sessions/{session.public_id}/invitations/{invitation.id}/send",
        follow_redirects=False,
    )
    assert response.headers["location"].endswith("/invitations?email=failed&kind=forbidden")
    [row] = db.execute(select(EmailOutbox)).scalars().all()
    assert row.status == "failed"
    assert "Microsoft refused" in client.get(response.headers["location"]).text


def test_the_operators_email_settings_reach_a_per_row_send(
    client: TestClient, db: Session, fake_mailer: FakeMailer
) -> None:
    session = _ready_session(client, db, code="row-options")
    operator = db.get(User, session.created_by_user_id)
    assert operator is not None
    operator.preferences = {"email_bcc_self": True, "email_save_to_sent_items": True}
    db.commit()
    invitation = _invitation(db, session.id)
    client.post(f"/operator/sessions/{session.public_id}/invitations/{invitation.id}/send")
    [message] = fake_mailer.sent
    assert operator.email in message.bcc
    assert message.save_to_sent_items is True


def test_a_regenerate_between_queue_and_send_stops_the_dead_link(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch, fake_mailer: FakeMailer
) -> None:
    """Codex on #3651: another operator's Regenerate, committed after the
    row was queued and before it was claimed, fails the row, so the old
    link never goes out."""
    from app.services import invitations as invitations_service
    from app.web.routes_operator import _operations

    session = _ready_session(client, db, code="row-superseded")
    invitation = _invitation(db, session.id)
    operator = db.get(User, session.created_by_user_id)
    assert operator is not None
    real_send_queued = _operations._send_queued_row  # pyright: ignore[reportPrivateUsage]  -- the seam under test

    def regenerate_first(*args: object, **kwargs: object) -> object:
        invitations_service.regenerate_token(db, invitation=invitation, user=operator)
        return real_send_queued(*args, **kwargs)  # pyright: ignore[reportArgumentType]  -- passed through

    monkeypatch.setattr(_operations, "_send_queued_row", regenerate_first)
    response = client.post(
        f"/operator/sessions/{session.public_id}/invitations/{invitation.id}/send",
        follow_redirects=False,
    )
    assert response.headers["location"].endswith("/invitations?email=superseded")
    assert fake_mailer.sent == []
    [row] = db.execute(select(EmailOutbox)).scalars().all()
    assert row.status == "failed"
    assert row.error_message == invitations_service.SUPERSEDED_MESSAGE
    assert "regenerated first" in client.get(response.headers["location"]).text


class _Refusing:
    def send_mail(self, message: MailMessage) -> None:
        raise GraphError("server", 503)


def test_a_refused_send_leaves_the_row_pending_with_its_send(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Findings M1: the invitation is stamped before the send, so a
    refused one used to read ``sent`` with no Send on its row."""
    monkeypatch.setattr(graph, "mailer_for", lambda _request, settings=None: _Refusing())
    session = _ready_session(client, db, code="row-m1-send")
    invitation = _invitation(db, session.id)
    base = f"/operator/sessions/{session.public_id}/invitations"
    response = client.post(f"{base}/{invitation.id}/send", follow_redirects=False)
    assert response.headers["location"].endswith("/invitations?email=failed&kind=server")
    db.refresh(invitation)
    assert invitation.status == "pending"
    assert invitation.sent_at is None
    reverted = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "invitation.send_reverted")
    ).scalar_one()
    assert reverted.detail is not None
    assert reverted.detail["context"] == {"restored": "status,sent_at"}
    assert f'action="{base}/{invitation.id}/send"' in client.get(base).text


def test_a_refused_reminder_leaves_last_reminder_at_as_it_was(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch, fake_mailer: FakeMailer
) -> None:
    session = _ready_session(client, db, code="row-m1-remind")
    invitation = _invitation(db, session.id)
    base = f"/operator/sessions/{session.public_id}/invitations"
    client.post(f"{base}/{invitation.id}/send")
    monkeypatch.setattr(graph, "mailer_for", lambda _request, settings=None: _Refusing())
    response = client.post(f"{base}/{invitation.id}/remind", follow_redirects=False)
    assert response.headers["location"].endswith("/invitations?email=failed&kind=server")
    db.refresh(invitation)
    assert invitation.status == "sent"
    assert invitation.last_reminder_at is None


def test_a_second_send_is_refused_and_the_first_link_lives(
    client: TestClient, db: Session, fake_mailer: FakeMailer
) -> None:
    """Findings L1: a double click mailed twice, minting a new token each
    time, so the first message's link was dead on arrival."""
    from app.services import invitations as invitations_service

    session = _ready_session(client, db, code="row-l1")
    invitation = _invitation(db, session.id)
    url = f"/operator/sessions/{session.public_id}/invitations/{invitation.id}/send"
    client.post(url)
    token = fake_mailer.sent[0].body.split("/invite/", 1)[1].split()[0].strip("\"'<>.,)")
    response = client.post(url, follow_redirects=False)
    assert response.headers["location"].endswith("/invitations?email=already_sent")
    assert len(fake_mailer.sent) == 1
    assert invitations_service.lookup_invitation_by_token(db, token) is not None
    assert "already sent, or is being sent" in client.get(response.headers["location"]).text


def test_an_open_during_a_refused_reminder_is_kept(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch, fake_mailer: FakeMailer
) -> None:
    """The restore puts back only what the send wrote and only while it
    still holds (the M1 fix's cold read): a reviewer who follows their
    link while the Graph call runs stays ``opened``."""
    session = _ready_session(client, db, code="row-m1-open")
    invitation = _invitation(db, session.id)
    base = f"/operator/sessions/{session.public_id}/invitations"
    client.post(f"{base}/{invitation.id}/send")

    class OpenedThenRefused:
        def send_mail(self, message: MailMessage) -> None:
            db.refresh(invitation)
            invitation.status = "opened"
            invitation.opened_at = invitation.sent_at
            db.commit()
            raise GraphError("server", 503)

    monkeypatch.setattr(graph, "mailer_for", lambda _request, settings=None: OpenedThenRefused())
    client.post(f"{base}/{invitation.id}/remind")
    db.refresh(invitation)
    assert invitation.status == "opened"
    assert invitation.opened_at is not None
    assert invitation.last_reminder_at is None
