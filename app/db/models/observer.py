from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.review_session import ReviewSession


class Observer(Base, TimestampMixin):
    """Per-session observer roster — the third participant audience.

    Mirrors the ``reviewers`` shape so the importer / Setup-page
    table / sort primitive / friendly-label resolver extend with
    no new patterns. ``email`` is the auth-bearing identity; an
    observer with no email has no reason to exist (unlike
    reviewees, whose confidential-subject case keeps the value
    NULL — see ``guide/archive/participant_model_upgrade.md`` §3.1).

    Single ``tag_1`` (not three) — observer use cases today are
    single-axis. Column name kept as ``tag_1`` so a future
    multi-tag extension is a pure addition rather than a rename
    (§3.1 "Why one tag, not three").

    Lands inert per ``guide/archive/participant_model_upgrade.md`` Phase 1;
    the Observer Setup page, Quick Setup slot, and surface
    populate this table in Phase 2 / Phase 3.
    """

    __tablename__ = "observers"
    __table_args__ = (
        UniqueConstraint("session_id", "email", name="uq_observer_session_email"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id"), index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    tag_1: Mapped[str | None] = mapped_column(String(255))

    session: Mapped[ReviewSession] = relationship(back_populates="observers")
