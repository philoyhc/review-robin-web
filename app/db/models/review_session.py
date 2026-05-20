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

    # Stamp set when the session transitions ``draft|validated →
    # ready`` (Segment 17B Phase 2 PR A). Used as the **Start**
    # column on the reviewer lobby — once Segment 18G ships
    # scheduled activation the same column will show the planned
    # open time pre-activation and the actual stamp afterwards.
    # ``NULL`` until the session is first activated.
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Segment 18G Part 0a — anchor datetime columns. The operator
    # sets these directly; every Part 0b offset is anchored on one
    # of them (or on the already-live ``deadline``). See
    # ``spec/lifecycle.md`` §8 "Scheduled lifecycle automation".
    # Both nullable, both inert at Part 0 — no service module
    # reads or writes these until the consumer Part lights them up.
    #
    # ``scheduled_activate_at`` is the **operator-set trigger** for
    # the scheduled ``validated → ready`` transition (Part 3); the
    # existing ``activated_at`` above is the **system-stamped
    # record** of when activation actually fired. Two columns, one
    # for each side of the trigger/record split.
    scheduled_activate_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # The Participants-platform "reviewees can view responses from
    # this point" anchor — pre-positioned inert so future
    # participant-model work doesn't need a follow-on migration.
    # No 18G Part reads it.
    responses_release_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Segment 18G Part 0b — offset config columns. Anchor-relative
    # operator-set offsets persisted as ISO 8601 duration strings
    # (e.g. ``-P1D``, ``-PT2H``, ``P30D``). Lists for events that
    # fire on a sequence (invites, reminders); singletons for
    # events that fire once (archive, release-until). See
    # ``spec/lifecycle.md`` §8 for the anchor table + the
    # cross-cutting anchor-null inertness rule.
    #
    # ``String(16)`` sizes the singletons generously past the
    # 10-day max offset (e.g. ``-PT240H`` is 7 chars). All four
    # columns are nullable and inert at Part 0 — no service module
    # reads or writes these until the consumer Part lights them up.
    invite_offsets: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    reminder_offsets: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    archive_offset: Mapped[str | None] = mapped_column(String(16), nullable=True)
    release_until_offset: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Segment 18G Part 0c — per-session retention controls.
    # ``retention_exception`` opts a session out of any auto-purge
    # (e.g. legal hold); ``NULL`` and ``False`` both mean "no
    # exception" (Part 4 normalises on read).
    # ``retention_overrides`` overrides the deployment retention
    # env-vars per-session, and also carries the per-session
    # ``delete_after_archive`` offset (ISO 8601 duration anchored
    # on the system-stamped archive timestamp). ``NULL`` means
    # "use the deployment defaults". Both columns inert at Part 0.
    retention_exception: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    retention_overrides: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

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
