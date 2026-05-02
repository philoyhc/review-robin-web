from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.assignment import Assignment
    from app.db.models.audit_event import AuditEvent
    from app.db.models.instrument import Instrument
    from app.db.models.invitation import Invitation
    from app.db.models.response_type_definition import ResponseTypeDefinition
    from app.db.models.reviewee import Reviewee
    from app.db.models.reviewer import Reviewer
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
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="session")
