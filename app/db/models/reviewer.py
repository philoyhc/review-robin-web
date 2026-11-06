from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.assignment import Assignment
    from app.db.models.invitation import Invitation
    from app.db.models.review_session import ReviewSession


class Reviewer(Base, TimestampMixin):
    __tablename__ = "reviewers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    profile_link: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    tag_1: Mapped[str | None] = mapped_column(String(255))
    tag_2: Mapped[str | None] = mapped_column(String(255))
    tag_3: Mapped[str | None] = mapped_column(String(255))
    # The directory account the address resolved to at upload (segment
    # 21F); all three empty when it did not resolve. The object ID binds.
    directory_object_id: Mapped[str | None] = mapped_column(String(64), index=True)
    directory_mail: Mapped[str | None] = mapped_column(String(320))
    directory_upn: Mapped[str | None] = mapped_column(String(320))
    # 14F rung 3d: when the reviewer last opened their review, through
    # the session link or a personal one; stamped at most once per
    # ``reviewers.ARRIVAL_GAP`` of surface GETs (``reviewers.mark_opened``).
    # ``Invitation.opened_at`` is the first follow of one invitation's link only.
    last_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    session: Mapped[ReviewSession] = relationship(back_populates="reviewers")
    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="reviewer",
        cascade="all, delete-orphan",
    )
    invitations: Mapped[list[Invitation]] = relationship(
        back_populates="reviewer",
        cascade="all, delete-orphan",
    )
