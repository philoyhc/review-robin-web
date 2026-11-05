"""The outbox dispatcher (segment 14F rung 2, `app/services/email_dispatch.py`)
and the Graph transport under it.

- A queued row is claimed, sent once and stamped `sent`, with `email.sent`.
- A failed send stamps `failed` with the operator-facing reason, and
  `email.send_failed` carries the transport's own.
- A row already `sending`, `sent` or `failed` is not claimed and not sent.
- The operator's options reach the message: Bcc to themselves (once),
  Reply-to, and Sent Items.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, EmailOutbox, Invitation, Reviewer, ReviewSession
from app.services import email_dispatch
from app.services import invitations as invitations_service
from app.services.email_dispatch import SendOptions
from app.services.email_send import GraphEmailTransport
from cordware.graph import FakeMailer, GraphError, MailMessage

from .test_scheduled_invites import (
    _generate_invitations,
    _operator,
    _seed_session_with_reviewers,
    _stub_build_url,
)


class RefusingMailer:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.calls = 0

    def send_mail(self, message: MailMessage) -> None:
        self.calls += 1
        raise GraphError(self.kind, 403 if self.kind == "forbidden" else None)


def _queued_row(db: Session, code: str) -> tuple[ReviewSession, EmailOutbox]:
    rs = _seed_session_with_reviewers(db, code, reviewer_count=1)
    op = _operator(db, rs)
    _generate_invitations(db, rs, op)
    invitation = (
        db.execute(select(Invitation).where(Invitation.session_id == rs.id)).scalars().first()
    )
    assert invitation is not None
    reviewer = db.get(Reviewer, invitation.reviewer_id)
    assert reviewer is not None
    sent = invitations_service.send_invitation(
        db,
        invitation=invitation,
        review_session=rs,
        reviewer=reviewer,
        user=op,
        build_invite_url=_stub_build_url,
    )
    row = db.get(EmailOutbox, sent.outbox_id)
    assert row is not None and row.status == "queued"
    return rs, row


def _events(db: Session, rs: ReviewSession, event_type: str) -> list[AuditEvent]:
    stmt = select(AuditEvent).where(
        AuditEvent.session_id == rs.id, AuditEvent.event_type == event_type
    )
    return list(db.execute(stmt).scalars())


def test_a_queued_row_is_sent_once_and_stamped(db: Session) -> None:
    rs, row = _queued_row(db, "disp-ok")
    mailer = FakeMailer()
    result = email_dispatch.dispatch(
        db, row, GraphEmailTransport(mailer), backend="graph", actor_user_id=rs.created_by_user_id
    )
    assert result.outcome == "sent"
    db.refresh(row)
    assert (row.status, row.backend, row.error_message) == ("sent", "graph", None)
    assert row.sent_at is not None
    assert [m.to for m in mailer.sent] == [row.to_email]
    assert mailer.sent[0].subject == row.subject and mailer.sent[0].body == row.body
    [event] = _events(db, rs, "email.sent")
    assert event.detail is not None
    assert event.detail["refs"]["outbox_id"] == row.id

    again = email_dispatch.dispatch(
        db, row, GraphEmailTransport(mailer), backend="graph", actor_user_id=None
    )
    assert again.outcome == "not_claimed"
    assert len(mailer.sent) == 1


def test_a_refused_send_is_stamped_failed_with_its_reason(db: Session) -> None:
    rs, row = _queued_row(db, "disp-fail")
    mailer = RefusingMailer("forbidden")
    result = email_dispatch.dispatch(
        db, row, GraphEmailTransport(mailer), backend="graph", actor_user_id=None
    )
    assert result.outcome == "failed"
    db.refresh(row)
    assert row.status == "failed"
    assert row.error_message == "Microsoft refused to send this from your mailbox."
    [event] = _events(db, rs, "email.send_failed")
    assert event.detail is not None
    assert event.detail["reason"].startswith("forbidden (403)")
    assert not _events(db, rs, "email.sent")


@pytest.mark.parametrize("status", ["sending", "sent", "failed"])
def test_a_row_not_queued_is_not_claimed(db: Session, status: str) -> None:
    _rs, row = _queued_row(db, f"disp-{status}")
    row.status = status
    db.commit()
    mailer = FakeMailer()
    result = email_dispatch.dispatch(
        db, row, GraphEmailTransport(mailer), backend="graph", actor_user_id=None
    )
    assert result.outcome == "not_claimed"
    assert mailer.sent == []
    db.refresh(row)
    assert row.status == status


def test_the_operators_options_reach_the_message(db: Session) -> None:
    _rs, row = _queued_row(db, "disp-opts")
    row.cc_emails = "dean@example.edu"
    row.bcc_emails = "Op@Example.edu, other@example.edu"
    db.commit()
    mailer = FakeMailer()
    options = SendOptions(
        save_to_sent_items=True, bcc_self="op@example.edu", reply_to="help@example.edu"
    )
    email_dispatch.dispatch(
        db, row, GraphEmailTransport(mailer), backend="graph", actor_user_id=None, options=options
    )
    [sent] = mailer.sent
    assert sent.cc == ("dean@example.edu",)
    assert sent.bcc == ("Op@Example.edu", "other@example.edu")  # the operator once
    assert sent.reply_to == "help@example.edu"
    assert sent.save_to_sent_items is True


def test_options_default_to_off(db: Session) -> None:
    _rs, row = _queued_row(db, "disp-defaults")
    mailer = FakeMailer()
    email_dispatch.dispatch(
        db, row, GraphEmailTransport(mailer), backend="graph", actor_user_id=None
    )
    [sent] = mailer.sent
    assert (sent.reply_to, sent.save_to_sent_items) == (None, False)


def test_send_options_follow_the_operators_choices() -> None:
    from app.db.models import User

    operator = User(email="op@example.edu", display_name="Op")
    review_session = ReviewSession(name="S", code="X", help_contact="help@example.edu")
    assert email_dispatch.send_options_for(operator, review_session) == SendOptions()
    operator.preferences = {
        "email_save_to_sent_items": True,
        "email_bcc_self": True,
        "email_reply_to_help": True,
    }
    assert email_dispatch.send_options_for(operator, review_session) == SendOptions(
        save_to_sent_items=True, bcc_self="op@example.edu", reply_to="help@example.edu"
    )


@pytest.mark.parametrize(
    ("help_contact", "reply_to"),
    [
        ("Dr Tan <tan@example.edu>", "tan@example.edu"),
        ("Dr Tan, room 3", None),
        (None, None),
        ("a@b@c", None),
    ],
)
def test_reply_to_applies_only_to_an_address(
    help_contact: str | None, reply_to: str | None
) -> None:
    from app.db.models import User

    operator = User(email="op@example.edu", preferences={"email_reply_to_help": True})
    review_session = ReviewSession(name="S", code="X", help_contact=help_contact)
    assert email_dispatch.send_options_for(operator, review_session).reply_to == reply_to
