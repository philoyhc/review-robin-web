from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.assignment import Assignment
    from app.db.models.review_session import ReviewSession


class Reviewee(Base, TimestampMixin):
    __tablename__ = "reviewees"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email_or_identifier: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
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
    results_acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Segment 20B: under symmetric review, the reviewer this reviewee
    # mirrors. The reconcile matches on it, so an address correction
    # updates the same row; turning the mode off clears it.
    mirrors_reviewer_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "reviewers.id",
            ondelete="SET NULL",
            name="fk_reviewees_mirrors_reviewer_id_reviewers",
        ),
        index=True,
        nullable=True,
    )

    session: Mapped[ReviewSession] = relationship(back_populates="reviewees")
    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="reviewee",
        cascade="all, delete-orphan",
    )
