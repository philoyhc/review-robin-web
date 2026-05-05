from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.audit_event import AuditEvent
    from app.db.models.review_session import ReviewSession
    from app.db.models.session_operator import SessionOperator


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    external_principal_id: Mapped[str | None] = mapped_column(String(255), index=True)

    # Per-operator SMTP credentials (Segment 11E PR 4). Send-as-me
    # identity model: the operator who initiates a send in Manage
    # Invitations sends from their own mailbox. ``smtp_password_encrypted``
    # is ``cryptography.fernet`` ciphertext keyed off the
    # ``SMTP_ENCRYPTION_KEY`` env var; plaintext is never persisted.
    smtp_host: Mapped[str | None] = mapped_column(String(255))
    smtp_port: Mapped[int | None] = mapped_column(Integer)
    smtp_username: Mapped[str | None] = mapped_column(String(320))
    smtp_password_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    smtp_from_display_name: Mapped[str | None] = mapped_column(String(255))
    smtp_encryption: Mapped[str | None] = mapped_column(String(16))
    smtp_transport: Mapped[str | None] = mapped_column(
        String(16), default="smtp", server_default="smtp"
    )

    review_sessions: Mapped[list[ReviewSession]] = relationship(
        back_populates="created_by_user",
        cascade="all, delete-orphan",
    )
    session_operators: Mapped[list[SessionOperator]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="actor")
