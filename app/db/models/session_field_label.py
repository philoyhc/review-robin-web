"""Per-session friendly-label overrides for tag / pair-context fields.

Backs Segment 15A's pervasive friendly-label resolver: each row
overrides the default display label for a single
``(source_type, source_field)`` pair within one session. The
resolver in ``app/services/field_labels.py`` (Slice 1 of 15A)
consults this table on every header / picker / tooltip render;
absence of a row falls back to a built-in default in code, then
to the literal ``source_type:source_field`` string.

Lands inert in Segment 13D PR 1 — no service module reads or
writes the table; the existing ``_DEFAULT_DISPLAY_LABELS`` dict
in ``app/services/instruments/_display_fields.py`` keeps its
current behaviour. 15A Slice 1 introduces the resolver.

See ``guide/segment_15A_friendly_labels.md`` Slice 1 for the
end-to-end design and ``guide/segment_13D_db_prep.md`` PR 1 for
the schema rationale.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.review_session import ReviewSession


class SessionFieldLabel(Base):
    __tablename__ = "session_field_labels"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "source_type",
            "source_field",
            name="uq_session_field_label",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    """``reviewer`` | ``reviewee`` | ``pair_context``. The 15A
    resolver enum; widening to ``assignment_context`` is gated on
    15B Slice 7 (deferred — see
    ``guide/segment_15B_per_instrument_assignments.md``)."""
    source_field: Mapped[str] = mapped_column(String(64), nullable=False)
    """e.g. ``tag_1`` / ``tag_2`` / ``tag_3`` for the tag sources;
    ``1`` / ``2`` / ``3`` for ``pair_context``."""
    label: Mapped[str] = mapped_column(String(255), nullable=False)

    session: Mapped[ReviewSession] = relationship()
