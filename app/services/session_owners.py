"""Per-session owner management — Segment 16B PR 2.

Read + write helpers behind the new "Owners" section on the
session edit page. Owners manage their session's roster of
co-owners; sys-admins reach the same surface via the relaxed
``require_sys_admin_or_session_operator`` gate so they can
self-add to any session in the workspace (then act on it via
the normal operator routes).

Service-layer invariants:

- **add_owner**: target must be a workspace operator
  (``is_operator OR is_sys_admin``); must not already be on
  ``session_operators`` for this session. Raises
  ``OwnerOperationError`` with codes ``not_in_workspace`` or
  ``already_owner``.
- **remove_owner**: refuses if the target is the only remaining
  owner (``code='last_owner'``). Self-remove is allowed except
  when self IS the last owner.

Each mutation writes a canonical 11K-envelope audit event
(``session.owner_added`` / ``session.owner_removed``) with the
target user id under ``refs.target_user_id`` and the actor on
``actor_user_id``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionOperator, User
from app.services import audit


@dataclass(frozen=True)
class OwnerRow:
    user_id: int
    email: str
    display_name: str | None
    role: str
    joined_at: datetime


class OwnerOperationError(ValueError):
    """Raised when a session-owner mutation violates an invariant.

    ``code`` is a stable machine identifier the route handler
    translates to an HTTP status; ``message`` is the
    human-readable explanation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def list_owners(db: Session, review_session: ReviewSession) -> list[OwnerRow]:
    """All current owners of ``review_session``, ordered by
    ``created_at ASC`` (creator typically appears first)."""
    rows = db.execute(
        select(SessionOperator, User)
        .join(User, User.id == SessionOperator.user_id)
        .where(SessionOperator.session_id == review_session.id)
        .order_by(SessionOperator.created_at.asc())
    ).all()
    return [
        OwnerRow(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=sess_op.role,
            joined_at=sess_op.created_at,
        )
        for sess_op, user in rows
    ]


def workspace_operator_candidates(
    db: Session, review_session: ReviewSession
) -> list[User]:
    """Workspace operators NOT yet on this session's owner list.
    Drives the Add-owner typeahead picker."""
    member_ids = {
        row.user_id for row in list_owners(db, review_session)
    }
    candidates = db.execute(
        select(User)
        .where((User.is_operator.is_(True)) | (User.is_sys_admin.is_(True)))
        .order_by(User.email.asc())
    ).scalars()
    return [u for u in candidates if u.id not in member_ids]


def add_owner(
    db: Session,
    *,
    review_session: ReviewSession,
    actor: User,
    target: User,
    correlation_id: str | None = None,
) -> SessionOperator:
    if not (target.is_operator or target.is_sys_admin):
        raise OwnerOperationError(
            code="not_in_workspace",
            message=(
                f"{target.email} is not on the workspace operator "
                "allowlist. Admit them via the Admin → Accounts "
                "Management page first."
            ),
        )
    existing = db.execute(
        select(SessionOperator).where(
            SessionOperator.session_id == review_session.id,
            SessionOperator.user_id == target.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise OwnerOperationError(
            code="already_owner",
            message=f"{target.email} is already an owner of this session.",
        )
    row = SessionOperator(
        session_id=review_session.id,
        user_id=target.id,
        role="owner",
    )
    db.add(row)
    db.flush()
    audit.write_event(
        db,
        event_type="session.owner_added",
        summary=f"Added {target.email} as owner of session {review_session.code}",
        actor_user_id=actor.id,
        session=review_session,
        payload=audit.snapshot(
            {"user_id": target.id, "email": target.email, "role": "owner"}
        ),
        refs={"target_user_id": target.id},
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(row)
    return row


def remove_owner(
    db: Session,
    *,
    review_session: ReviewSession,
    actor: User,
    target: User,
    correlation_id: str | None = None,
) -> None:
    # SELECT FOR UPDATE serialises concurrent removes through the
    # last-owner guard: two simultaneous POSTs both reading
    # ``count == 2`` would otherwise both pass the check and each
    # delete one row, leaving the session with zero owners. Locking
    # the full owner set before counting + deleting makes the
    # invariant atomic on Postgres (the deployed dialect); SQLite
    # ignores ``FOR UPDATE`` silently — fine for tests, no
    # concurrency to race in-process.
    locked_rows = db.execute(
        select(SessionOperator)
        .where(SessionOperator.session_id == review_session.id)
        .with_for_update()
    ).scalars().all()
    target_row = next(
        (r for r in locked_rows if r.user_id == target.id), None
    )
    if target_row is None:
        raise OwnerOperationError(
            code="not_owner",
            message=f"{target.email} is not an owner of this session.",
        )
    if len(locked_rows) <= 1:
        raise OwnerOperationError(
            code="last_owner",
            message=(
                "Refusing to remove the only remaining owner. Add a "
                "second owner before removing this one."
            ),
        )
    db.delete(target_row)
    db.flush()
    audit.write_event(
        db,
        event_type="session.owner_removed",
        summary=f"Removed {target.email} as owner of session {review_session.code}",
        actor_user_id=actor.id,
        session=review_session,
        payload=audit.snapshot(
            {"user_id": target.id, "email": target.email, "role": target_row.role}
        ),
        refs={"target_user_id": target.id},
        correlation_id=correlation_id,
    )
    db.commit()
