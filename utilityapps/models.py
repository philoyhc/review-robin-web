"""Utilities' tables (segment U4)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from utilityapps.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class PhotoPocPhoto(Base):
    """One saved photo of the photo upload proof of concept: the server's
    own re-encoded crop, never the upload (`utilityapps/guide/archive/
    segment_U4_photo_poc.md`, Semantics)."""

    __tablename__ = "photo_poc_photos"
    __table_args__ = (UniqueConstraint("public_id", name="uq_photo_poc_photos_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(16), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
