from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.invitation import Invitation
    from app.db.models.review_session import ReviewSession
    from app.db.models.reviewer import Reviewer


# Canonical value sets for the ``status`` and ``kind`` string columns.
# Documented here so any future widening is a deliberate edit. Until
# Segment 14-1 Part A wires the dispatch helper, the enqueue paths only
# ever write ``"queued"`` (status) and ``"invitation"`` / ``"reminder"``
# (kind); the wider sets below are scaffolding for that work.
EMAIL_OUTBOX_STATUSES: tuple[str, ...] = ("queued", "sending", "sent", "failed")
EMAIL_OUTBOX_KINDS: tuple[str, ...] = ("invitation", "reminder", "responses_received")


class EmailOutbox(Base):
    """Audit-log row for an outbound email (invitation, reminder, or
    responses-received notification).

    Pre-Segment-14-1 the row is a dev-mode preview surface: there is no
    real transport, so ``status`` flips ``queued → sent`` synchronously
    when the row is written and the operator views the rendered body
    here. Segment 14-1 Part A lights up the actual send paths against
    the audit-log columns added by Segment 11C PR F (``error_message``,
    ``from_address``, ``backend``, ``backend_message_id``,
    ``delivered_at``, ``payload_hash``, ``correlation_id``); the value
    sets ``status`` and ``kind`` may take are documented above as
    ``EMAIL_OUTBOX_STATUSES`` / ``EMAIL_OUTBOX_KINDS``.

    See ``spec/email_infra_options.md`` "Audit log" for the field
    semantics and the broader transport landscape.
    """

    __tablename__ = "email_outbox"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id"), index=True, nullable=False
    )
    reviewer_id: Mapped[int | None] = mapped_column(
        ForeignKey("reviewers.id"), index=True, nullable=True
    )
    invitation_id: Mapped[int | None] = mapped_column(
        ForeignKey("invitations.id"), index=True, nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    to_email: Mapped[str] = mapped_column(String(320), nullable=False)
    cc_emails: Mapped[str | None] = mapped_column(Text, nullable=True)
    bcc_emails: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Audit-log scaffolding (Segment 11C PR F). All nullable; populated
    # by the Segment 14-1 dispatch helper, not by today's enqueue paths.
    # Truncated transport error captured on failure.
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The address actually sent from (operator-set or deployment default).
    from_address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # Which ``EmailTransport`` implementation handled the send
    # (``smtp`` / ``graph`` / ``acs`` / ``thirdparty:sendgrid`` / etc.).
    backend: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Backend's message identifier (Graph / ACS operation id, third-party
    # message id, SMTP server queue id). NULL when the backend reports none.
    backend_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # When delivery confirmed (Graph / ACS / third-party report this;
    # SMTP typically does not).
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Hash of (to, subject, body) for dedup detection.
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Deterministic identifier for "this send to this recipient at this
    # intent" — drives idempotent retry. Indexed because the dispatch
    # helper looks rows up by it.
    correlation_id: Mapped[str | None] = mapped_column(
        String(128), index=True, nullable=True
    )

    session: Mapped[ReviewSession] = relationship()
    reviewer: Mapped[Reviewer | None] = relationship()
    invitation: Mapped[Invitation | None] = relationship()
