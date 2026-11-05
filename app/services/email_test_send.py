"""Send a test to me: the composer's template, as edited, to the operator
(segment 14F rung 2b; author's ruling 2026-11-05).

- **As edited.** The subject and body on the form, saved or not, are what
  the test renders. They overlay the session's saved overrides for the
  one render, through ``set_committed_value``, so nothing is marked dirty
  and nothing is saved.
- **Merge tags** come from a sample row: the roster's first reviewer, or
  a stand-in named "Sample Reviewer" while the roster is empty. The
  invite link is a placeholder; a test never mints a token.
- **To** the signed-in operator only. The template's Cc and Bcc are not
  copied (nor the operator's own Bcc choice); their Sent Items and
  Reply-to choices apply. No outbox row is written: a test is not a send to a
  participant. ``email.test_sent`` records it, either way.
"""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.db.models import Reviewer, ReviewSession, User
from app.services import audit, email_dispatch, email_templates
from app.services.email_send import EmailMessage, EmailTransport, SendResult

SUBJECT_PREFIX = "[Test] "
SAMPLE_INVITE_URL = "(a test send: each reviewer's own link goes here)"
SAMPLE_REVIEWER_NAME = "Sample Reviewer"
TEMPLATES = ("invitation", "reminder", "responses_received")


def sample_reviewer(db: Session, review_session: ReviewSession) -> Reviewer:
    """The roster's first reviewer, or an unsaved stand-in."""
    first = (
        db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id).order_by(Reviewer.id)
        )
        .scalars()
        .first()
    )
    return first if first is not None else Reviewer(name=SAMPLE_REVIEWER_NAME, email="")


def render_as_edited(
    db: Session,
    review_session: ReviewSession,
    template: str,
    edited: Mapping[str, str | None],
) -> tuple[str, str]:
    """``(subject, body)`` for ``template`` with ``edited`` (override key →
    value, ``None`` or blank for "the default") over the saved overrides."""
    if template not in TEMPLATES:
        raise ValueError(f"unknown template {template!r}")
    saved = review_session.email_template_overrides
    overlay = dict(saved or {})
    for key, value in edited.items():
        if value is None or not value.strip():
            overlay.pop(key, None)
        else:
            overlay[key] = value
    reviewer = sample_reviewer(db, review_session)
    set_committed_value(review_session, "email_template_overrides", overlay)
    try:
        if template == "invitation":
            return email_templates.render_invitation(review_session, reviewer, SAMPLE_INVITE_URL)
        if template == "reminder":
            return email_templates.render_reminder(review_session, reviewer, SAMPLE_INVITE_URL)
        return email_templates.render_responses_received(review_session, reviewer)
    finally:
        set_committed_value(review_session, "email_template_overrides", saved)


def send_test(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    template: str,
    edited: Mapping[str, str | None],
    transport: EmailTransport,
    correlation_id: str | None = None,
) -> SendResult:
    """Render ``template`` as edited and send it to ``user``; audit it."""
    subject, body = render_as_edited(db, review_session, template, edited)
    # The operator's Sent Items and Reply-to choices apply, so the test
    # shows them; Bcc to themselves would only send it twice.
    options = email_dispatch.send_options_for(user, review_session)
    result = transport.send(
        EmailMessage(
            from_addr="",
            from_display_name=None,
            to=user.email,
            subject=SUBJECT_PREFIX + subject,
            body=body,
            reply_to=options.reply_to,
            save_to_sent_items=options.save_to_sent_items,
        )
    )
    audit.write_event(
        db,
        event_type="email.test_sent",
        summary=(
            f"Sent a test {template} email to {user.email}"
            if result.ok
            else f"Could not send a test {template} email to {user.email}"
        ),
        actor_user_id=user.id,
        session=review_session,
        severity="info" if result.ok else "warning",
        reason=None if result.ok else (result.transport_response or result.error_message),
        context={"template": template, "outcome": "sent" if result.ok else "failed"},
        correlation_id=correlation_id,
    )
    db.commit()
    return result
