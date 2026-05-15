from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.assignment import Assignment
    from app.db.models.audit_event import AuditEvent
    from app.db.models.email_outbox import EmailOutbox
    from app.db.models.instrument import Instrument
    from app.db.models.invitation import Invitation
    from app.db.models.response_type_definition import ResponseTypeDefinition
    from app.db.models.reviewee import Reviewee
    from app.db.models.reviewer import Reviewer
    from app.db.models.session_field_label import SessionFieldLabel
    from app.db.models.session_operator import SessionOperator
    from app.db.models.user import User


class ReviewSession(Base, TimestampMixin):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assignment_mode: Mapped[str | None] = mapped_column(String(32))
    self_reviews_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default=true()
    )
    help_contact: Mapped[str | None] = mapped_column(String(320))
    # Free-form JSON; recognised string-override keys live in
    # ``app.services.email_templates.OVERRIDE_KEYS``
    # (``invitation_*`` / ``reminder_*`` / ``responses_received_*``,
    # each with ``_subject`` / ``_body`` / ``_cc`` / ``_bcc`` variants).
    # Plus one bool flag — ``responses_received_enabled`` — gating the
    # post-submit confirmation auto-send (default ``True`` when absent;
    # consumed by Segment 11C Part 2 PR H).
    email_template_overrides: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    # Per-session display timezone (Segment 18B). An IANA zone
    # name (e.g. ``Asia/Singapore``) used to render this session's
    # dates / times. ``NULL`` means "inherit the creating
    # operator's default timezone" — load-bearing in 18B's
    # resolution order (session override -> operator default ->
    # UTC). Schema pre-positioned in 13F PR 6; lands inert — no
    # service module reads or writes the column until 18B PR 3
    # lights it up (per-session timezone card + create-time
    # stamping). Validity is enforced at the service layer
    # against ``zoneinfo.available_timezones()`` at light-up, not
    # by a DB CHECK constraint.
    display_timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )

    created_by_user: Mapped[User] = relationship(back_populates="review_sessions")
    operators: Mapped[list[SessionOperator]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    reviewers: Mapped[list[Reviewer]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    reviewees: Mapped[list[Reviewee]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    instruments: Mapped[list[Instrument]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    invitations: Mapped[list[Invitation]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    response_type_definitions: Mapped[list[ResponseTypeDefinition]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    field_labels: Mapped[list[SessionFieldLabel]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    # ``email_outbox`` rows carry FKs to both ``sessions`` and the
    # session-scoped ``invitations`` they originated from. Without an
    # ORM-level cascade here, ``ReviewSession`` deletion blocks on the
    # FK from ``email_outbox.invitation_id`` to ``invitations.id``
    # (the unit-of-work tries to flush invitation deletes first and
    # SQLite/Postgres reject them while outbox rows still reference
    # the invitations). Cascading from the session deletes outbox
    # rows before invitations, breaking the cycle.
    email_outbox_rows: Mapped[list[EmailOutbox]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="session")
