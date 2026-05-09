from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.assignment import Assignment
    from app.db.models.instrument_field import (
        InstrumentDisplayField,
        InstrumentResponseField,
    )
    from app.db.models.review_session import ReviewSession


class Instrument(Base, TimestampMixin):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_label: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(String(2000))
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accepting_responses: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    responses_visible_when_closed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    deadline_closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    rule_set_id: Mapped[int | None] = mapped_column(
        ForeignKey("session_rule_sets.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    """The per-session ``session_rule_sets`` row currently applied to
    this instrument (Segment 15B). NULL = "no RuleSet currently
    selected" — the initial state for every existing instrument
    post-13D PR 4 and the state after a reset-assignments action.

    Targets the per-session copy table, not the operator library
    (``operator_rule_sets``), so deleting an instrument disposes
    of the pointer without touching the session's RuleSet copy,
    and deleting from the operator library doesn't touch any
    instrument pointer (session copies survive library deletes
    via ``session_rule_sets.library_origin_id`` SET NULL — see
    13D PR 2)."""

    session: Mapped[ReviewSession] = relationship(back_populates="instruments")
    display_fields: Mapped[list[InstrumentDisplayField]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
        order_by="InstrumentDisplayField.order",
    )
    response_fields: Mapped[list[InstrumentResponseField]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
        order_by="InstrumentResponseField.order",
    )
    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
    )
