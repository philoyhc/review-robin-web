from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HeldUpload(Base):
    """One uploaded file held across an ask (segment 19W).

    An upload refused with a question (a missing replace tick, a
    group-clear count, the Settings import's deletion count) keeps the
    files of that submit here under one ``token``, one row per ``slot``,
    so the operator answers the question without choosing the file
    again. Postgres-backed for the same reason as ``RehydrateStash``: the
    ask and the answer may land on different App Service instances.

    A row belongs to one operator and one session; the service finds it
    only by its token together with both, and the FK cascades drop it
    with either. Rows expire an hour after ``created_at``
    (``app.services.held_uploads.HOLD_TTL``).
    """

    __tablename__ = "held_uploads"
    __table_args__ = (
        UniqueConstraint("token", "slot", name="uq_held_uploads_token_slot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    slot: Mapped[str] = mapped_column(String(32), nullable=False)
    operator_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
