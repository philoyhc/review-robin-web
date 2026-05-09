"""ORM models for the RuleBased assignment library.

Two tables: ``rule_sets`` carries the named RuleSet metadata (scope,
owner, soft-delete, latest-revision pointer), and ``rule_set_revisions``
carries the rule tree as a JSON column with one row per Save. See
``guide/segment_13A_rulebased_assignment_builder.md`` §"DB shape" for
the rationale on why the rule tree lives as JSON inside one revision
row rather than normalised into per-rule tables.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class RuleSet(Base, TimestampMixin):
    """A named RuleSet — seeded or operator-authored.

    The ``current_revision_id`` pointer indirects to the latest
    ``rule_set_revisions`` row; older revisions are retained because
    past ``assignments.generated`` audit rows pin a specific revision
    id (see PR 6's revisioning model).
    """

    __tablename__ = "operator_rule_sets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    scope: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    """``seed`` or ``personal`` — see ``app/schemas/rules.py::RuleSetScope``."""
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    """NULL for seeds; the importing user's id for Personal RuleSets."""
    is_seed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    current_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("rule_set_revisions.id", use_alter=True), nullable=True
    )
    """Points at the row in ``rule_set_revisions`` whose tree is the
    "current" version. NULL only during the brief window between
    ``rule_sets`` insert and the first revision insert."""
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """Soft-delete marker. Set on operator delete; library list filters
    rows where ``deleted_at IS NOT NULL``. Audit-ref resolution does
    not filter — past ``assignments.generated`` rows still resolve."""

    owner: Mapped[User | None] = relationship("User", foreign_keys=[owner_user_id])
    revisions: Mapped[list[RuleSetRevision]] = relationship(
        back_populates="rule_set",
        cascade="all, delete-orphan",
        foreign_keys="RuleSetRevision.rule_set_id",
        order_by="RuleSetRevision.revision_no",
    )
    current_revision: Mapped[RuleSetRevision | None] = relationship(
        "RuleSetRevision",
        foreign_keys=[current_revision_id],
        post_update=True,
    )


class RuleSetRevision(Base):
    """One revision (Save event) of a RuleSet.

    The rule tree lives as a JSON column; the structured shape is
    documented in ``app/schemas/rules.py::RuleSetSchema``.
    """

    __tablename__ = "rule_set_revisions"
    __table_args__ = (
        UniqueConstraint(
            "rule_set_id", "revision_no", name="uq_rule_set_revision_no"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rule_set_id: Mapped[int] = mapped_column(
        ForeignKey("operator_rule_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
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
    """Serialised rule tree. Empty list = no content rules
    (e.g. seeded ``Full Matrix``)."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    rule_set: Mapped[RuleSet] = relationship(
        back_populates="revisions", foreign_keys=[rule_set_id]
    )
    created_by: Mapped[User | None] = relationship(
        "User", foreign_keys=[created_by_user_id]
    )
