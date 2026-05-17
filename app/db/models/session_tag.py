from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SessionTag(Base):
    """Free-form operator-chosen tag on a session (Segment 13F PR 3).

    Lands inert — no service module reads or writes this table until
    Segment 18A Part 2 lights it up (lobby tag-filter chips + the
    Add / Remove tag affordance). ``(session_id, tag)`` is unique so a
    session cannot carry the same tag twice; the row is
    ``ON DELETE CASCADE`` so deleting a session drops its tags.
    """

    __tablename__ = "session_tags"
    __table_args__ = (
        UniqueConstraint("session_id", "tag", name="uq_session_tag_session_tag"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tag: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
