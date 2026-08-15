from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RehydrateStash(Base):
    """Short-lived server-side stash of an uploaded extract file set,
    holding it between the rehydrate **Validate** and **Rehydrate**
    (commit) requests (Segment 18P PR G2).

    Postgres-backed rather than a local temp file so the two-request
    hand-off survives App Service scale-out (a Validate on one instance
    and a Commit on another must find the same set) — see
    ``docs/rehydrate.md`` §3.3. ``payload`` is the operator's file set
    serialized to a single opaque blob (a re-zipped bundle; the shape is
    the caller's concern). Rows are swept past their TTL and deleted
    after a successful commit; the FK cascade drops them with the
    operator's user row.

    ``LargeBinary`` (not a Postgres-specific type) keeps the model
    dialect-portable per the ``app/db/models`` convention.
    """

    __tablename__ = "rehydrate_stashes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    operator_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
