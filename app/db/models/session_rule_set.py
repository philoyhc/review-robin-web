"""Per-session RuleSet rows — backing store for Band 1's inline
rule editor on new-model instruments.

Wave 5 PR 5.2 stripped the library tier:

- ``operator_rule_sets`` + ``rule_set_revisions`` tables dropped.
- ``library_origin_id`` provenance FK + the paired ``is_seeded``
  spec-lock column dropped.
- The eligibility cache columns
  (``cached_eligible_pair_count`` / ``cached_eligibility_stamp``)
  dropped — the helper that wrote them retired in PR 5.1.

What remains: a thin per-session table that Band 1's inline
editor writes to (and that ``instruments.rule_set_id`` pins
into for both new-model authored rules and legacy carry-over).
The assignment engine reads ``rules_json`` directly.
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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.review_session import ReviewSession


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

    combinator: Mapped[str] = mapped_column(String(16), nullable=False)
    """``ALL_OF`` / ``ANY_OF`` / ``PIPELINE`` — see
    ``app/schemas/rules.py::Combinator``."""
    exclude_self_reviews: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """Global RNG seed for any RANDOM-strategy quota rule whose own
    selection seed is unset."""
    rules_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False
    )
    """Serialised rule tree. Empty list = Full Matrix (no
    content rules)."""

    session: Mapped[ReviewSession] = relationship()
