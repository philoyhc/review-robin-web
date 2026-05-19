from __future__ import annotations

from typing import TYPE_CHECKING, Any

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
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
    sort_display_fields: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )
    """Operator-defined default sort spec for this instrument's
    reviewer-surface table (Segment 13B). Each entry shapes as
    ``{"display_field_id": int, "dir": "asc"|"desc"}`` per the
    canonical functional spec at ``spec/sort_by_reviewee.md``.
    NULL or ``[]`` = "no operator default" (the reviewer-surface
    render falls back to its current sort policy of instrument
    order then insertion order). Maximum 3 entries; service-layer
    ``instruments.set_sort_display_fields`` enforces length /
    duplicate / cross-instrument-id / direction validators.

    Column shipped inert in Segment 13D PR 5 (#701, 2026-05-09);
    13B PR 1 (#TBD) lit up the reviewer-surface render-path
    consumer + the service writer."""
    group_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    """Group-scoping flag + group-boundary spec for Segment 13C's
    group-scoped instruments — one shared answer covers a whole
    group of reviewees instead of per-reviewee. NULL = "regular
    per-reviewee instrument". Any non-null value flags the
    instrument group-scoped.

    The non-null value encodes the group-boundary spec: an ordered,
    comma-joined list of tag key-codes (``r1``-``r3`` reviewee
    tags, ``p1``-``p3`` pair-context tags) — e.g. ``r1`` or
    ``r1,p2``. A reviewer's rule-eligible universe is partitioned
    into groups by the shared values of those boundary tags
    (additive). A group-scoped instrument with no boundary tag
    keeps the sentinel ``"both"`` so the column stays non-null.
    Encoded / decoded by ``app.services.instruments`` —
    ``encode_group_kind`` / ``decode_group_kind`` /
    ``set_group_boundary``. See ``spec/group_scoped_instruments.md``."""
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

    cached_group_pair_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    cached_group_pair_stamp: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    """Lazy persisted cache for the reviewer-group pair count shown
    on a group-scoped instrument's rule card (Segment 13C PR 4
    slice 4b). ``cached_group_pair_stamp`` is a content-hash of the
    roster + the pinned rule's definition + ``group_kind``; a
    mismatch on read recomputes. Per-instrument (not per-rule, like
    ``session_rule_sets.cached_eligible_pair_count``) because the
    count depends on the instrument's boundary tags. Both NULL on a
    per-reviewee instrument or an un-pinned one — never populated."""

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
