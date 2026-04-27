from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.audit_event import AuditEvent
    from app.db.models.review_session import ReviewSession
    from app.db.models.session_operator import SessionOperator


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    external_principal_id: Mapped[str | None] = mapped_column(String(255), index=True)

    review_sessions: Mapped[list[ReviewSession]] = relationship(
        back_populates="created_by_user",
        cascade="all, delete-orphan",
    )
    session_operators: Mapped[list[SessionOperator]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="actor")
