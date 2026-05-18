"""Per-session snapshot copies of RuleSets.

Library / per-session-copy split (Segment 15C):

- ``operator_rule_sets`` is the operator-library tier — RuleSets
  visible across all of an operator's sessions.
- ``session_rule_sets`` (this table) is the per-session copy
  tier — what an instrument actually applies via
  ``instruments.rule_set_id`` (added in 13D PR 4).

Each row carries a complete snapshot of the rule tree at copy /
edit time. There is **no** per-session revisions table — RTDs
are minimalistic, the same call applied to RuleSets here for
symmetry. Operators preserving history is an explicit "Save to
library" action that creates a new revision in
``rule_set_revisions`` on the library side. The
``library_origin_id`` FK is **provenance only**; deleting the
referenced library row clears it via ``SET NULL`` and the
session copy survives unchanged.

Lands inert in Segment 13D PR 2 — no service module reads or
writes the table; the existing Rule Builder + assignments-
generation pipeline stays pointed at ``operator_rule_sets`` (via
the ``RuleSet`` class) until 15C reroutes it.

See ``guide/segment_13D_db_prep.md`` PR 2 for the schema
rationale, ``guide/segment_15C_operator_libraries.md`` for the
end-to-end library / copy design, and
``guide/segment_15B_per_instrument_assignments.md`` Slice 2 for
how ``instruments.rule_set_id`` will point into this table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.review_session import ReviewSession
    from app.db.models.rule_set import RuleSet


class SessionRuleSet(Base, TimestampMixin):
    __tablename__ = "session_rule_sets"

    __table_args__ = (
        UniqueConstraint(
            "session_id", "name", name="uq_session_rule_set_session_name"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default=""
    )

    # ----- Snapshot of the rule tree (mirrors RuleSetRevision). -----
    combinator: Mapped[str] = mapped_column(String(16), nullable=False)
    """``ALL_OF`` / ``ANY_OF`` / ``PIPELINE`` — see
    ``app/schemas/rules.py::Combinator``."""
    exclude_self_reviews: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """Global RNG seed for any RANDOM-strategy quota rule whose own
    selection seed is unset."""
    is_seeded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    """``True`` when the row was materialised from a workspace-
    shipped seed in ``SEEDED_RULE_SETS`` (15C Slice 1). Seed copies
    are spec-locked: the service layer refuses ``update`` / ``rename``
    / ``delete`` / ``save_to_library`` calls on them, mirroring the
    RTD spec-lock model (``response_type_definitions.is_seeded``).
    Operators customise a seed by Copy → Save-As, which writes a
    fresh row with ``is_seeded=False``."""
    rules_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False
    )
    """Serialised rule tree — same shape as
    ``rule_set_revisions.rules_json``. Empty list = no content
    rules (e.g. a snapshot of the seeded ``Full Matrix``)."""

    # ----- Provenance pointer back to the library row. -----
    library_origin_id: Mapped[int | None] = mapped_column(
        ForeignKey("operator_rule_sets.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    """The ``operator_rule_sets.id`` this row was copied from, or
    NULL if the row was authored directly in the session (or its
    library origin has since been deleted). Provenance-only — the
    column is never read for resolution."""

    # ----- Lazy persisted eligibility cache (perf). -----
    cached_eligible_pair_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    """Last computed "eligible pairs" count for this rule. NULL =
    never computed (cache miss). Written by
    ``session_library.evaluate_session_rule_eligibility``; never
    authoritative — it is recomputed whenever the stamp below
    no longer matches the current inputs."""

    cached_eligibility_stamp: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    """Content-hash of the inputs (reviewer / reviewee /
    relationship rows + this rule's definition) that
    ``cached_eligible_pair_count`` was computed from. A mismatch
    on read means the cache is stale."""

    session: Mapped[ReviewSession] = relationship()
    library_origin: Mapped[RuleSet | None] = relationship()
