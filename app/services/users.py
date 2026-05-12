"""Workspace user-role management — Segment 16A PR 6.

Read + write helpers behind the Accounts Management tab on the
Admin chrome. Callers gate on ``require_sys_admin``; this module
trusts that gate and does not re-check it.

The four toggles (Admit / Revoke / Promote / Demote) each flip
one Boolean on a ``users`` row, emit a canonical audit event,
and apply the invariants:

- The actor may not act on their own row (``UserOperationError``
  with code ``self_action``). Operator self-revoke / sole sys-
  admin demote risks are sidestepped by routing all such cases
  through "ask another admin".
- ``demote`` refuses if the target is the only remaining sys-
  admin (``UserOperationError`` with code ``last_admin``).
- ``revoke`` refuses if the target still owns sessions
  (``still_owner``) — operator clears the session memberships
  via ``remove_from_all_sessions`` first.
- ``remove_from_all_sessions`` refuses if the target is the
  sole owner of any session (``sole_owner``).
- ``remove_user`` (hard delete) refuses if the target owns any
  session (``owns_sessions``).
- Other invariants (Promote-when-already-admin, etc.) are
  no-ops at the column level; the calling route forms hide the
  irrelevant button per row.

``invite`` creates a pre-seeded ``users`` row before the invitee's
first Entra sign-in. ``get_or_create_user`` matches by email on
sign-in, so the pre-seeded row picks up the principal at that
point without overriding the flags this module set.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import SessionOperator, User
from app.services import audit


@dataclass(frozen=True)
class WorkspaceUserRow:
    id: int
    email: str
    display_name: str | None
    is_operator: bool
    is_sys_admin: bool
    created_at: datetime
    session_operator_count: int
    sole_owner_count: int


class UserOperationError(ValueError):
    """Raised when a workspace-role mutation violates an
    invariant. ``code`` is a stable machine identifier route
    handlers translate to HTTP status codes; ``message`` is the
    human-readable explanation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def list_workspace_users(db: Session) -> list[WorkspaceUserRow]:
    """Every users row + per-user session-operator + sole-owner
    counts. Ordered by ``id DESC`` so newly-admitted users surface
    at the top.

    ``session_operator_count`` is the total number of sessions
    where the user appears as an operator (any role).
    ``sole_owner_count`` is the number of those sessions that
    list exactly one operator (i.e. the user is the only owner) —
    drives the "Remove from all sessions" + "Delete user" gates
    on the operator UI.
    """
    # One sweep over session_operators is enough to compute both
    # per-user totals and per-session operator counts (which then
    # back the sole-owner derivation). Operator workspaces stay
    # small (tens of users × tens of sessions), so an in-Python
    # aggregate is cheaper than a window-function query that
    # SQLite has to fake.
    op_rows = list(
        db.execute(select(SessionOperator.session_id, SessionOperator.user_id))
    )
    session_total: dict[int, int] = defaultdict(int)
    for session_id, _ in op_rows:
        session_total[session_id] += 1
    user_total: dict[int, int] = defaultdict(int)
    user_sole: dict[int, int] = defaultdict(int)
    for session_id, user_id in op_rows:
        user_total[user_id] += 1
        if session_total[session_id] == 1:
            user_sole[user_id] += 1

    users = (
        db.execute(select(User).order_by(User.id.desc())).scalars().all()
    )
    return [
        WorkspaceUserRow(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            is_operator=user.is_operator,
            is_sys_admin=user.is_sys_admin,
            created_at=user.created_at,
            session_operator_count=user_total.get(user.id, 0),
            sole_owner_count=user_sole.get(user.id, 0),
        )
        for user in users
    ]


def _guard_self(actor: User, target: User) -> None:
    if actor.id == target.id:
        raise UserOperationError(
            code="self_action",
            message=(
                "You can't change your own roles. Ask another sys-admin "
                "to flip your flags."
            ),
        )


def _sys_admin_count(db: Session) -> int:
    return int(
        db.execute(
            select(func.count(User.id)).where(User.is_sys_admin.is_(True))
        ).scalar_one()
    )


def admit(
    db: Session,
    *,
    actor: User,
    target: User,
    correlation_id: str | None = None,
) -> None:
    _guard_self(actor, target)
    old = target.is_operator
    target.is_operator = True
    audit.write_event(
        db,
        event_type="workspace.operator_admitted",
        summary=f"Admitted {target.email} as operator",
        actor_user_id=actor.id,
        payload=audit.changes({"is_operator": [old, True]}),
        refs={"target_user_id": target.id},
        correlation_id=correlation_id,
    )
    db.commit()


def revoke(
    db: Session,
    *,
    actor: User,
    target: User,
    correlation_id: str | None = None,
) -> None:
    """Flip ``is_operator`` off on a workspace user.

    Refuses when the target still appears on any
    ``session_operators`` row (``still_owner``). The operator
    clears those memberships via ``remove_from_all_sessions``
    first; revoking the workspace flag while sessions still
    reference the user would leave the sessions in an
    inconsistent state where a non-operator owns a session.
    """
    _guard_self(actor, target)
    owned = int(
        db.execute(
            select(func.count(SessionOperator.id)).where(
                SessionOperator.user_id == target.id
            )
        ).scalar_one()
    )
    if owned > 0:
        raise UserOperationError(
            code="still_owner",
            message=(
                f"Refusing to revoke operator status from "
                f"{target.email} while they own "
                f"{owned} session{'s' if owned != 1 else ''}. "
                "Use 'Remove from all sessions' first."
            ),
        )
    old = target.is_operator
    target.is_operator = False
    audit.write_event(
        db,
        event_type="workspace.operator_revoked",
        summary=f"Revoked operator status from {target.email}",
        actor_user_id=actor.id,
        payload=audit.changes({"is_operator": [old, False]}),
        refs={"target_user_id": target.id},
        correlation_id=correlation_id,
    )
    db.commit()


def promote(
    db: Session,
    *,
    actor: User,
    target: User,
    correlation_id: str | None = None,
) -> None:
    _guard_self(actor, target)
    old = target.is_sys_admin
    target.is_sys_admin = True
    audit.write_event(
        db,
        event_type="sys_admin.role_promoted",
        summary=f"Promoted {target.email} to sys-admin",
        actor_user_id=actor.id,
        payload=audit.changes({"is_sys_admin": [old, True]}),
        refs={"target_user_id": target.id},
        correlation_id=correlation_id,
    )
    db.commit()


def demote(
    db: Session,
    *,
    actor: User,
    target: User,
    correlation_id: str | None = None,
) -> None:
    _guard_self(actor, target)
    if _sys_admin_count(db) <= 1 and target.is_sys_admin:
        raise UserOperationError(
            code="last_admin",
            message=(
                "Refusing to demote the only sys-admin in the workspace. "
                "Promote another user to sys-admin before demoting this one."
            ),
        )
    old = target.is_sys_admin
    target.is_sys_admin = False
    audit.write_event(
        db,
        event_type="sys_admin.role_demoted",
        summary=f"Demoted {target.email} from sys-admin",
        actor_user_id=actor.id,
        payload=audit.changes({"is_sys_admin": [old, False]}),
        refs={"target_user_id": target.id},
        correlation_id=correlation_id,
    )
    db.commit()


def remove_from_all_sessions(
    db: Session,
    *,
    actor: User,
    target: User,
    correlation_id: str | None = None,
) -> int:
    """Strip the target from every session they own.

    Guards:

    - ``self_action`` — operators can't act on themselves.
    - ``sole_owner`` — refuses when the target is the only
      operator of any session (removing them would leave that
      session orphaned). Operator transfers / co-owns those
      sessions first.

    Returns the number of ``session_operators`` rows deleted.
    A no-op (already detached from every session) succeeds
    silently and returns ``0`` without emitting an audit event.
    """
    _guard_self(actor, target)

    rows = list(
        db.execute(
            select(SessionOperator).where(SessionOperator.user_id == target.id)
        ).scalars()
    )
    if not rows:
        return 0

    # Sole-owner check: any session this user appears on whose
    # total operator count is 1 is sole-ownership.
    session_ids = [r.session_id for r in rows]
    counts = dict(
        db.execute(
            select(
                SessionOperator.session_id,
                func.count(SessionOperator.id),
            )
            .where(SessionOperator.session_id.in_(session_ids))
            .group_by(SessionOperator.session_id)
        ).all()
    )
    sole_ids = sorted(sid for sid, c in counts.items() if c == 1)
    if sole_ids:
        raise UserOperationError(
            code="sole_owner",
            message=(
                f"Refusing to detach {target.email}: they are the sole "
                f"owner of {len(sole_ids)} "
                f"session{'s' if len(sole_ids) != 1 else ''}. "
                "Add another owner to those sessions first."
            ),
        )

    deleted_session_ids = sorted(session_ids)
    for row in rows:
        db.delete(row)
    db.flush()
    audit.write_event(
        db,
        event_type="workspace.user_detached_from_all_sessions",
        summary=(
            f"Removed {target.email} from {len(rows)} "
            f"session{'s' if len(rows) != 1 else ''}"
        ),
        actor_user_id=actor.id,
        payload=audit.counts(sessions_detached=len(rows)),
        refs={"target_user_id": target.id},
        context={
            "session_ids": ",".join(str(sid) for sid in deleted_session_ids),
        },
        correlation_id=correlation_id,
    )
    db.commit()
    return len(rows)


def remove_user(
    db: Session,
    *,
    actor: User,
    target: User,
    correlation_id: str | None = None,
) -> None:
    """Hard-delete a workspace ``users`` row.

    Guards:

    - ``self_action`` — operators can't remove themselves.
    - ``last_admin`` — refuses to remove the only remaining
      sys-admin in the workspace.
    - ``owns_sessions`` — refuses when the user owns one or
      more sessions (``session_operator_count > 0``). The
      operator transfers or deletes those sessions first.

    On success the row is hard-deleted and a
    ``workspace.user_removed`` snapshot audit event records the
    last-known role state and the deleted email.
    """
    _guard_self(actor, target)
    if target.is_sys_admin and _sys_admin_count(db) <= 1:
        raise UserOperationError(
            code="last_admin",
            message=(
                "Refusing to remove the only sys-admin in the workspace. "
                "Promote another user to sys-admin before removing this one."
            ),
        )
    owned = int(
        db.execute(
            select(func.count(SessionOperator.id)).where(
                SessionOperator.user_id == target.id
            )
        ).scalar_one()
    )
    if owned > 0:
        raise UserOperationError(
            code="owns_sessions",
            message=(
                f"Refusing to remove {target.email} while they own "
                f"{owned} session{'s' if owned != 1 else ''}. "
                "Transfer or delete those sessions first."
            ),
        )

    snapshot = {
        "email": target.email,
        "is_operator": target.is_operator,
        "is_sys_admin": target.is_sys_admin,
    }
    target_id = target.id
    target_email = target.email
    db.delete(target)
    db.flush()
    audit.write_event(
        db,
        event_type="workspace.user_removed",
        summary=f"Removed {target_email} from the workspace",
        actor_user_id=actor.id,
        payload=audit.snapshot(snapshot),
        refs={"target_user_id": target_id},
        correlation_id=correlation_id,
    )
    db.commit()


def invite(
    db: Session,
    *,
    actor: User,
    email: str,
    is_operator: bool = True,
    is_sys_admin: bool = False,
    correlation_id: str | None = None,
) -> User:
    """Pre-seed a ``users`` row before the invitee's first Entra
    sign-in. Email match is case-insensitive against existing
    rows; raises ``UserOperationError(code="duplicate")`` when a
    row already exists. Sys-admin invitees implicitly get
    ``is_operator=True``."""
    email_normalised = email.strip()
    if not email_normalised or "@" not in email_normalised:
        raise UserOperationError(
            code="invalid_email",
            message=f"'{email}' is not a valid email address.",
        )
    existing = db.execute(
        select(User).where(func.lower(User.email) == email_normalised.lower())
    ).scalar_one_or_none()
    if existing is not None:
        raise UserOperationError(
            code="duplicate",
            message=(
                f"A user with email {email_normalised} already exists. "
                "Use the row's toggle buttons to change their roles."
            ),
        )

    if is_sys_admin:
        is_operator = True
    user = User(
        email=email_normalised,
        is_operator=is_operator,
        is_sys_admin=is_sys_admin,
    )
    db.add(user)
    db.flush()
    audit.write_event(
        db,
        event_type="workspace.user_invited",
        summary=f"Invited {user.email} (operator={is_operator}, sys_admin={is_sys_admin})",
        actor_user_id=actor.id,
        payload=audit.snapshot(
            {
                "email": user.email,
                "is_operator": is_operator,
                "is_sys_admin": is_sys_admin,
            }
        ),
        refs={"target_user_id": user.id},
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(user)
    return user
