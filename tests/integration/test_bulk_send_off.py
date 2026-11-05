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
from app.db.models import EmailOutbox, Invitation, User
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
