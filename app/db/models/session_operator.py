from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.review_session import ReviewSession
    from app.db.models.user import User


# Locked value-set for ``SessionOperator.role`` (Segment 13F PR 4).
# Today only ``"owner"`` is written by any code path
# (``sessions.create_session`` inserts the creator as owner at
# create-time). ``"manager"`` is reserved for the future
# less-rights-than-owner role surfaced in Segment 16B; widening
# this tuple is a deliberate Python edit, gated at the
# service-layer write-path (no DB CHECK — matches the
# ``EMAIL_OUTBOX_STATUSES`` / ``EMAIL_OUTBOX_KINDS`` precedent).
SESSION_OPERATOR_ROLES: tuple[str, ...] = ("owner", "manager")


class SessionOperator(Base):
    __tablename__ = "session_operators"
    __table_args__ = (UniqueConstraint("session_id", "user_id", name="uq_session_user"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), default="owner", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[ReviewSession] = relationship(back_populates="operators")
    user: Mapped[User] = relationship(back_populates="session_operators")
