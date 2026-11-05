"""Send one outbox row through a transport, once (segment 14F rung 2).

The outbox row is already rendered: its ``to_email``, ``subject``,
``body`` and ``bcc_emails`` are what the enqueue paths wrote. This
module claims it, sends it and stamps the outcome:

1. **Claim.** One conditional update flips the row ``queued`` →
   ``sending`` and commits, so a resubmit rewriting a still-``queued``
   row, or two overlapping clicks of Send all, cannot send it twice
   (14F Semantics, "One send per row"). A row not ``queued`` is not
   claimed and not sent.
2. **Send** through the ``EmailTransport``, which returns a result and
   never raises.
3. **Stamp** ``sent`` with ``sent_at``, or ``failed`` with the reason,
   plus ``backend`` and ``from_address``, and write ``email.sent`` /
   ``email.send_failed``. Commits.

A request that dies between 1 and 3 leaves the row ``sending``; the
outbox shows it so, and only a person retries it.

Per-operator options (14C Item 2's toggles) come in as ``SendOptions``,
which ``send_options_for`` builds from the operator's stored choices.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parseaddr
from typing import Literal

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.models import EmailOutbox, ReviewSession, User
from app.db.session import rowcount
from app.services import audit, operator_settings
from app.services.email_identity import looks_like_email
from app.services.email_send import EmailMessage, EmailTransport

Outcome = Literal["sent", "failed", "not_claimed"]


@dataclass(frozen=True)
class SendOptions:
    """What the sending operator chose (14C Item 2), all off by default."""

    save_to_sent_items: bool = False
    bcc_self: str | None = None
    reply_to: str | None = None


def _address(text: str | None) -> str | None:
    """``text`` as one email address, or ``None``: a help contact is free
    text ("Dr Tan, room 3"), and only an address can be a Reply-to."""
    raw = (text or "").strip()
    _name, address = parseaddr(raw)
    # ``parseaddr`` squeezes out spaces outside angle brackets, so
    # "tan@x.edu or call 6516" comes back as one run of text: accept it
    # only when the text is the address alone or ``Name <address>``.
    if not looks_like_email(address):
        return None
    if raw != address and not raw.endswith(f"<{address}>"):
        return None
    return address


def send_options_for(user: User, review_session: ReviewSession) -> SendOptions:
    """What ``user``'s Email settings choices mean for a send in
    ``review_session`` (14C Item 2). The Reply-to choice applies only
    when the session's Help contact is an email address."""
    preferences = operator_settings.get_email_preferences(user)
    return SendOptions(
        save_to_sent_items=preferences.save_to_sent_items,
        bcc_self=user.email if preferences.bcc_self else None,
        reply_to=_address(review_session.help_contact) if preferences.reply_to_help else None,
    )


@dataclass(frozen=True)
class DispatchResult:
    outcome: Outcome
    error_message: str | None = None


def _addresses(raw: str | None) -> list[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def message_for(row: EmailOutbox, options: SendOptions) -> EmailMessage:
    """The transport's message for ``row``, with the operator's options.
    The sender is the operator's mailbox, so ``from_addr`` is left for
    the transport to ignore."""
    bcc = _addresses(row.bcc_emails)
    if options.bcc_self and options.bcc_self.lower() not in {a.lower() for a in bcc}:
        bcc.append(options.bcc_self)
    return EmailMessage(
        from_addr="",
        from_display_name=None,
        to=row.to_email,
        subject=row.subject,
        body=row.body,
        cc=_addresses(row.cc_emails),
        bcc=bcc,
        reply_to=options.reply_to,
        save_to_sent_items=options.save_to_sent_items,
    )


def claim(db: Session, row: EmailOutbox) -> bool:
    """Flip ``row`` ``queued`` → ``sending`` and commit; whether this
    call claimed it."""
    claimed = (
        rowcount(
            db.execute(
                update(EmailOutbox)
                .where(EmailOutbox.id == row.id, EmailOutbox.status == "queued")
                .values(status="sending")
                .execution_options(synchronize_session=False)
            )
        )
        == 1
    )
    db.commit()
    db.refresh(row)
    return claimed


def dispatch(
    db: Session,
    row: EmailOutbox,
    transport: EmailTransport,
    *,
    backend: str,
    actor_user_id: int | None,
    options: SendOptions,
    from_address: str | None = None,
    now: datetime | None = None,
) -> DispatchResult:
    """Claim ``row``, send it, stamp it. See the module docstring.
    ``options`` is required, so a caller cannot drop the operator's
    Email settings by omission: pass ``send_options_for(user, session)``."""
    if not claim(db, row):
        return DispatchResult("not_claimed")
    result = transport.send(message_for(row, options))
    row.backend = backend
    row.from_address = from_address
    refs = {"outbox_id": row.id}
    if row.invitation_id is not None:
        refs["invitation_id"] = row.invitation_id
    if row.reviewer_id is not None:
        refs["reviewer_id"] = row.reviewer_id
    if result.ok:
        row.status = "sent"
        row.sent_at = now or datetime.now(UTC)
        row.error_message = None
        audit.write_event(
            db,
            event_type="email.sent",
            summary=f"Sent {row.kind} email #{row.id} to {row.to_email}",
            actor_user_id=actor_user_id,
            session=row.session,
            refs=refs,
            context={"kind": row.kind, "backend": backend},
        )
    else:
        row.status = "failed"
        row.error_message = result.error_message
        audit.write_event(
            db,
            event_type="email.send_failed",
            summary=f"Could not send {row.kind} email #{row.id} to {row.to_email}",
            actor_user_id=actor_user_id,
            session=row.session,
            severity="warning",
            reason=result.transport_response or result.error_message,
            refs=refs,
            context={"kind": row.kind, "backend": backend},
        )
    db.commit()
    return DispatchResult("sent" if result.ok else "failed", result.error_message)
