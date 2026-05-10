"""Per-pair attributes table — the post-15D home for pair-context tags.

Replaces ``Assignment.context.pair_context_*`` as the join between
a reviewer / reviewee pair and operator-typed tag values, lifted
out of the assignments table so per-pair attributes exist
independently of whether the rule engine has materialised an
assignment for the pair.

Lands inert in Segment 13E PR 2 — no service module reads or
writes the table; the existing ``Assignment.context`` JSON
remains the authoritative source until 15D wires the per-entity
importer + generation consumption + the one-time backfill.

See ``guide/segment_13E_db_prep.md`` PR 2 for the schema
rationale and ``guide/segment_15D_assignments_revamp.md`` for the
end-to-end design.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.review_session import ReviewSession
    from app.db.models.reviewee import Reviewee
    from app.db.models.reviewer import Reviewer


class Relationship(Base, TimestampMixin):
    __tablename__ = "relationships"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "reviewer_id",
            "reviewee_id",
            name="uq_relationships_session_reviewer_reviewee",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    reviewer_id: Mapped[int] = mapped_column(
        ForeignKey("reviewers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    reviewee_id: Mapped[int] = mapped_column(
        ForeignKey("reviewees.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tag_1: Mapped[str | None] = mapped_column(String(255))
    tag_2: Mapped[str | None] = mapped_column(String(255))
    tag_3: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(32), default="active", nullable=False, server_default="active"
    )

    session: Mapped[ReviewSession] = relationship()
    reviewer: Mapped[Reviewer] = relationship()
    reviewee: Mapped[Reviewee] = relationship()
