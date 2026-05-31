from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.assignment import Assignment
    from app.db.models.invitation import Invitation
    from app.db.models.review_session import ReviewSession


class Reviewer(Base, TimestampMixin):
    __tablename__ = "reviewers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    profile_link: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    tag_1: Mapped[str | None] = mapped_column(String(255))
    tag_2: Mapped[str | None] = mapped_column(String(255))
    tag_3: Mapped[str | None] = mapped_column(String(255))

    session: Mapped[ReviewSession] = relationship(back_populates="reviewers")
    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="reviewer",
        cascade="all, delete-orphan",
    )
    invitations: Mapped[list[Invitation]] = relationship(
        back_populates="reviewer",
        cascade="all, delete-orphan",
    )
