from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.instrument import Instrument
    from app.db.models.response import Response
    from app.db.models.review_session import ReviewSession
    from app.db.models.reviewee import Reviewee
    from app.db.models.reviewer import Reviewer


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "reviewer_id",
            "reviewee_id",
            "instrument_id",
            name="uq_assignment_unique",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id"), index=True, nullable=False
    )
    reviewer_id: Mapped[int] = mapped_column(
        ForeignKey("reviewers.id"), index=True, nullable=False
    )
    reviewee_id: Mapped[int] = mapped_column(
        ForeignKey("reviewees.id"), index=True, nullable=False
    )
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id"), index=True, nullable=False
    )
    include: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # ``context: JSON`` retired in 15D PR 6b. ``pair_context_*`` keys
    # lifted to the ``relationships`` table; ``assignment_context_*``
    # keys retired entirely (operator-typed via the manual CSV only).
    created_by_mode: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[ReviewSession] = relationship(back_populates="assignments")
    reviewer: Mapped[Reviewer] = relationship(back_populates="assignments")
    reviewee: Mapped[Reviewee] = relationship(back_populates="assignments")
    instrument: Mapped[Instrument] = relationship(back_populates="assignments")
    responses: Mapped[list[Response]] = relationship(
        back_populates="assignment",
        cascade="all, delete-orphan",
    )
