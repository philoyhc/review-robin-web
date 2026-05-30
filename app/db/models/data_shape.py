"""``DataShape`` — operator-saved Data shaper shapes.

Per the wiring decisions in ``spec/extract_data.md``
"Wiring decisions (resolved 2026-05-29)" — Data shapes are
per-session library entries that the operator composes via
the Data shaper card and downloads as CSVs. Each row is one
saved shape; the unique constraint on ``(session_id, name)``
prevents the operator from saving two shapes with the same
name on the same session.

Foreign keys CASCADE on every side:

* ``session_id`` — deleting a session drops its shapes.
* ``instrument_id`` — deleting an instrument drops every
  shape scoped to it. The operator re-authors the shape on
  the new instrument set.
* ``response_field_id`` — same for response fields.

CASCADE is the cleaner default vs. SET NULL because a shape
that silently widens its scope when its anchor instrument /
field disappears is more surprising than a shape that simply
vanishes.

Saved shapes are part of session settings — they round-trip
through the Settings CSV export / import per the Settings
section in the wiring decisions (lands in a later PR).
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    true as sa_true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class DataShape(Base, TimestampMixin):
    __tablename__ = "data_shapes"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "name", name="uq_data_shape_session_name"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Axis is the row-key driver: ``reviewer`` ⇒ one row per
    # reviewer (or per reviewer-tag-combo, depending on the
    # column-chip selection); ``reviewee`` ⇒ symmetric. See
    # spec/extract_data.md "Row-key contract" for the full
    # combinatorics.
    axis: Mapped[str] = mapped_column(String(16), nullable=False)
    # Scope-filter chips: nullable when the operator wants
    # aggregates across the entire session (no instrument
    # selected) or across every field on the chosen
    # instrument (no field selected).
    instrument_id: Mapped[int | None] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=True,
    )
    response_field_id: Mapped[int | None] = mapped_column(
        ForeignKey("instrument_response_fields.id", ondelete="CASCADE"),
        nullable=True,
    )
    # JSON list of column-chip slot strings (e.g.
    # ``["reviewer:name", "reviewer:email",
    # "reviewer:assigned", "reviewer:count"]``). Stored as
    # TEXT for SQLite compatibility — the application layer
    # JSON-encodes / decodes. Order matters: the slot order
    # drives the preview-row column order and the CSV header
    # order on extract.
    column_chip_slots: Mapped[str] = mapped_column(Text, nullable=False)
    # Self-review handling chip — three-state cycle persisted per
    # shape (``include_self`` / ``exclude_self`` / ``both``); see
    # ``guide/extract_data.md`` § *Self-review handling in
    # summarizing extracts*. PR B (#TBD) added the column with a
    # default of ``include_self`` so existing rows + chip-less
    # imports preserve today's behaviour. The file-gen path
    # (``app/services/extracts/data_shape_extract.py``) reads the
    # column to pick the column-name suffix + the in-pool filter.
    self_review_handling: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default="include_self",
        default="include_self",
    )
    # Empty-row drop chip — PR 6 of the chip-controlled-drop slice
    # per the self-review consolidation addendum. ``True`` (default)
    # surfaces every relevant row including rows whose accumulator
    # is empty; ``False`` drops empty rows (per-individual / per-
    # tag-combo row schemes only — single-summary always emits its
    # one row). Default ``True`` preserves today's behaviour for
    # existing shapes + chip-less Settings CSV imports.
    include_empty_rows: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=sa_true(),
        default=True,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
