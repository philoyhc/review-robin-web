"""Apply Desk's tables (segment AD2A): people, exercises, who operates
them, and the audit trail. The rest of an exercise still comes from
`applydesk/sample_data.py` until AD2B onward (`applydesk/guide/
ad2_series.md`)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from applydesk.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Person(Base):
    """Someone Apply Desk knows (ruling 73), bound by tenant and object ID
    once known; until then *pending*, found by `email_key` (the casefolded
    email) and bound at first sign-in. Email, UPN and name are snapshots.
    The operator allowlist is on the row (ruling 75): `may_operate`, set by
    the platform super-admin."""

    __tablename__ = "person"
    __table_args__ = (
        UniqueConstraint("tenant_id", "object_id", name="uq_person_tenant_object"),
        # One pending person per address (Codex on #4110); bound people may
        # share an address, theirs being a snapshot only.
        Index(
            "uq_person_pending_email",
            "email_key",
            unique=True,
            sqlite_where=text("object_id IS NULL"),
            postgresql_where=text("object_id IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64))
    object_id: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(320))
    email_key: Mapped[str | None] = mapped_column(String(320), index=True)
    upn: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(255))
    bound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    may_operate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    admitted_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("person.id", name="fk_person_admitted_by")
    )
    admitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def bound(self) -> bool:
        """Whether the person is tied to an account (tenant and object ID)."""
        return self.object_id is not None

    @property
    def label(self) -> str:
        """How pages name the person: their name, else their address."""
        return self.display_name or self.email or "Unknown person"


class Exercise(Base):
    """An exercise's key and public ID (AD-53: unique per table). AD2B
    adds its settings; until then they are the sample's."""

    __tablename__ = "exercise"
    __table_args__ = (UniqueConstraint("public_id", name="uq_exercise_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class ExerciseOperator(Base):
    """A person's grant on an exercise (ruling 73): one row per pair, its
    Owner marked. Removal sets `removed_at`; re-adding clears it. The rule
    of one current Owner is the service's (`applydesk/operators.py`), and
    the database's: a partial unique index allows one Owner row per
    exercise (an Owner is never removed, only replaced), so two handovers
    at once cannot both win (Codex on #4110)."""

    __tablename__ = "exercise_operator"
    __table_args__ = (
        UniqueConstraint("exercise_id", "person_id", name="uq_exercise_operator_pair"),
        Index(
            "uq_exercise_one_owner",
            "exercise_id",
            unique=True,
            sqlite_where=text("is_owner"),
            postgresql_where=text("is_owner"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercise.id", name="fk_exercise_operator_exercise"), nullable=False
    )
    person_id: Mapped[int] = mapped_column(
        ForeignKey("person.id", name="fk_exercise_operator_person"), nullable=False
    )
    is_owner: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    added_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("person.id", name="fk_exercise_operator_added_by")
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    """One audited change, in Review Robin's envelope (ruling 74): its type,
    who, on which exercise, and `detail`, validated against the event
    type's schema on write (`applydesk/audit.py`, rung 3)."""

    __tablename__ = "audit_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("person.id", name="fk_audit_event_actor")
    )
    exercise_id: Mapped[int | None] = mapped_column(
        ForeignKey("exercise.id", name="fk_audit_event_exercise"), index=True
    )
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
