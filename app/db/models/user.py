from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, Integer, LargeBinary, String, text
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

    # Workspace-level sys-admin flag (Segment 16A). Read by
    # ``require_sys_admin`` to gate the Sys Admin chrome + the
    # admin-only mutating surfaces (Manual assignment upload,
    # future SMTP test-send). Lit up by Segment 16A PRs 1-2; until
    # then this column sits inert. Bootstrap source on
    # first-sign-in is the ``SYS_ADMIN_EMAILS`` env var
    # (still owned by ``app/config.py``); the persisted column
    # is the live source of truth after that — removing an
    # email from the env var does NOT auto-demote.
    is_sys_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )

    # Workspace-level operator allowlist (Segment 16A, Option C
    # strict-allowlist access posture). Read by
    # ``require_operator`` (16A PR 1) — the gate on every
    # operator route. Predicate: ``is_operator OR is_sys_admin``
    # (sys-admin implies operator). Lit up by Segment 16A PR 1;
    # until then this column sits inert. Bootstrap source on
    # first-sign-in is the ``OPERATOR_EMAILS`` env var; the
    # persisted column is the live source of truth after that —
    # removing an email from the env var does NOT auto-revoke.
    # Revocation goes through 16A PR 6's workspace UI.
    is_operator: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )

    # Per-operator preferences container (Segment 18B). A JSON
    # object whose keys are individual operator-level display
    # preferences. First consumer: 18B PR 2 reads / writes the
    # ``display_timezone`` key (the operator's default timezone
    # for sessions they create). The container is deliberately
    # general — future operator-level display settings become new
    # keys, not new migrations. ``NULL`` (or an absent key) means
    # "no preference set"; the consumer falls through to its
    # in-code default (``UTC`` for the timezone key). Schema
    # pre-positioned in 13F PR 7; lands inert — no service module
    # reads or writes the column until 18B PR 2 lights it up.
    preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    @property
    def display_label(self) -> str:
        """The canonical "who is this user" label — the display name if
        set, else the email (always present; it's the identity column).
        One source for the ``display_name or email`` string that was
        hand-rolled across ~7 templates + a route (audit V3). The
        distinct ``display_name or "—"`` variant (name-only, email
        shown in an adjacent column) stays inline where it's used
        deliberately."""
        return self.display_name or self.email

    @property
    def is_super_admin(self) -> bool:
        """Segment 18S Item 1 — the protected top tier. Derived from
        config (``SUPER_ADMIN_EMAILS`` + the fake-auth fold-in), never a
        stored column, so it can't drift or be flipped in-app. Thin
        delegate to ``app.auth.roles`` (lazy import keeps the model's
        module-level dependency graph free of the auth layer)."""
        from app.auth.roles import is_super_admin

        return is_super_admin(self.email)

    review_sessions: Mapped[list[ReviewSession]] = relationship(
        back_populates="created_by_user",
        cascade="all, delete-orphan",
    )
    session_operators: Mapped[list[SessionOperator]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="actor")
