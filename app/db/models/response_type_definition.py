from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.instrument_field import InstrumentResponseField
    from app.db.models.review_session import ReviewSession


class ResponseTypeDefinition(Base):
    __tablename__ = "response_type_definitions"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "response_type", name="uq_rtd_session_name"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    response_type: Mapped[str] = mapped_column(String(64), nullable=False)
    data_type: Mapped[str] = mapped_column(String(16), nullable=False)
    min: Mapped[float | None] = mapped_column(Float, nullable=True)
    max: Mapped[float | None] = mapped_column(Float, nullable=True)
    step: Mapped[float | None] = mapped_column(Float, nullable=True)
    list_csv: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_seeded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    seed_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Segment 18J Wave 2 PR iii-b3 retired the operator RTD
    # library tier (the cross-session "Save to library" /
    # "Add from library" workflow). The ``library_origin_id``
    # provenance FK + the ``operator_response_type_definitions``
    # table were both dropped; per-session RTDs no longer carry
    # a cross-session provenance pointer.

    session: Mapped[ReviewSession] = relationship(
        back_populates="response_type_definitions"
    )
    response_fields: Mapped[list[InstrumentResponseField]] = relationship(
        back_populates="response_type_definition",
        # ``passive_deletes`` lets the database FK ``ON DELETE CASCADE``
        # handle dependent-row removal instead of having SQLAlchemy
        # NULL-out the FK column before the parent delete fires (which
        # would violate the column's NOT NULL constraint).
        passive_deletes=True,
    )
