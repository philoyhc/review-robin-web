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


class EmailOutbox(Base):
    """Dev-mode outbox for invitation (and future reminder) emails.

    In Segment 9.2 there is no real SMTP backend; the operator views the
    rendered email body (including the raw token URL) here. ``status``
    flips ``queued → sent`` synchronously when the row is written.
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

    session: Mapped[ReviewSession] = relationship()
    reviewer: Mapped[Reviewer | None] = relationship()
    invitation: Mapped[Invitation | None] = relationship()
