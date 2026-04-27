from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.assignment import Assignment
    from app.db.models.instrument_field import InstrumentResponseField


class Response(Base):
    __tablename__ = "responses"
    __table_args__ = (
        UniqueConstraint(
            "assignment_id", "response_field_id", name="uq_response_assignment_field"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id"), index=True, nullable=False
    )
    response_field_id: Mapped[int] = mapped_column(
        ForeignKey("instrument_response_fields.id"), index=True, nullable=False
    )
    value: Mapped[str | None] = mapped_column(Text)
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    assignment: Mapped[Assignment] = relationship(back_populates="responses")
    response_field: Mapped[InstrumentResponseField] = relationship(back_populates="responses")
