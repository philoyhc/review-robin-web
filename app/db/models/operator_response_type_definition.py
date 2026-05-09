"""Operator-library tier for Response Type Definitions.

Library / per-session-copy split (Segment 15C):

- ``operator_response_type_definitions`` (this table) is the
  operator-library tier — RTDs visible across all of an
  operator's sessions; auto-copied into a session's
  ``response_type_definitions`` rows on session create.
- ``response_type_definitions`` is the per-session copy tier —
  what an instrument's ``InstrumentResponseField.response_type_id``
  actually references.

The ``library_origin_id`` provenance pointer on the per-session
table (added in 13D PR 3) links a session copy back to the
library row it was cloned from. Provenance-only — never read for
resolution; survives library-row deletion via ``SET NULL``.

Mirrors the post-PR-0 ``operator_rule_sets`` shape on the
RuleSet side, minus revisioning. RTDs are minimalistic — a
1-5 Likert / 0-4.0 GPA decimal / etc. — so within-session edits
just update the per-session row in place. Operators preserving
history is an explicit "Save to library" action that creates a
new library row (or updates an existing one).

Lands inert in Segment 13D PR 3 — no service module reads or
writes the table or the new provenance column. The existing seed
materialisation
(``SEEDED_RESPONSE_TYPE_DEFINITIONS`` →
``ensure_default_response_type_definitions``) keeps its current
behaviour. 15C wires the auto-copy-on-session-create + Save-to-
library / Add-from-library flows.

See ``guide/segment_13D_db_prep.md`` PR 3 for the schema
rationale and ``guide/segment_15C_operator_libraries.md`` for
the end-to-end design.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class OperatorResponseTypeDefinition(Base, TimestampMixin):
    __tablename__ = "operator_response_type_definitions"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "response_type",
            name="uq_operator_rtd_owner_name",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    response_type: Mapped[str] = mapped_column(String(64), nullable=False)
    """Operator-chosen name (e.g. "Likert5", "GPA4")."""
    data_type: Mapped[str] = mapped_column(String(16), nullable=False)
    """``int`` / ``decimal`` / ``short_text`` / ``long_text`` /
    ``list``. Same value-set as ``response_type_definitions.data_type``."""
    min: Mapped[float | None] = mapped_column(Float, nullable=True)
    max: Mapped[float | None] = mapped_column(Float, nullable=True)
    step: Mapped[float | None] = mapped_column(Float, nullable=True)
    list_csv: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner: Mapped[User] = relationship()
