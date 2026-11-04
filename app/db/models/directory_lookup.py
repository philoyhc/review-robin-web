from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DirectoryLookup(Base):
    """One directory answer the server fetched for an upload's
    countdown (segment 20H Item 6).

    The roster Upload card's script looks the file's addresses up in
    batches before it posts the file; each answer the server got from
    Graph is kept here, so the upload reads it rather than asking again.
    Only answers are kept (an account, not found, ambiguous); a failed
    lookup is not, and the upload asks again. Postgres-backed for the
    same reason as ``HeldUpload``: the batches and the upload may land on
    different App Service instances.

    A row belongs to one operator and one session, the token's owner and
    the roster's; the FK cascades drop it with either. Rows are stale
    fifteen minutes after ``fetched_at``
    (``app.services.directory_lookups.CACHE_TTL``).
    """

    __tablename__ = "directory_lookups"
    __table_args__ = (
        UniqueConstraint(
            "operator_user_id", "session_id", "key",
            name="uq_directory_lookups_operator_session_key",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    operator_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    #: The lookup key: the address normalized (`directory_accounts.key`).
    key: Mapped[str] = mapped_column(String(320), nullable=False)
    #: `cordware.graph.Outcome`'s fields; the account's are empty when
    #: the answer named none.
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    match_type: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mail: Mapped[str | None] = mapped_column(String(320), nullable=True)
    upn: Mapped[str | None] = mapped_column(String(320), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
