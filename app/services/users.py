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
  admin (``UserOperationError`` with code ``last_admin``), and, like
  ``revoke``, if a target with no Operator flag still owns sessions
  (``still_owner``): the demote would take their operator access.
- ``revoke`` refuses if the target still owns sessions
  (``still_owner``) — operator clears the session memberships
  via ``remove_from_all_sessions`` first.
- ``remove_from_all_sessions`` refuses if the target is the
  sole owner of any session (``sole_owner``).
- ``remove_user`` (hard delete) refuses if the target owns any
  session (``owns_sessions``), or created one or acted in the audit
  log (``has_history``) — removal is for accounts with no activity.
- Other invariants (Promote-when-already-admin, etc.) are
  no-ops at the column level; the calling route forms hide the
  irrelevant button per row.

``invite`` creates a pre-seeded ``users`` row before the invitee's
first Entra sign-in. ``get_or_create_user`` matches by email on
sign-in (``find_signed_in_user``), so the invitee lands on the
pre-seeded row without overriding the flags this module set. The
row is stored with no principal id; that first sign-in records it, so
the principal-id match below reaches invited accounts too.

``find_signed_in_user`` matches the Entra object id before the email
(findings P5): the row whose ``external_principal_id`` matches takes a
changed email, so a user whose email claim changes keeps their flags
and session ownership.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.auth.roles import effective_super_admin_emails, is_super_admin
from app.db.models import (
    AuditEvent,
    DataShape,
    RehydrateStash,
    ReviewSession,
    SessionOperator,
    User,
)
from app.logging_config import get_logger
from app.services import audit
from app.services.email_identity import normalize_email

log = get_logger(__name__)


# SQL ``trim`` alone strips only spaces; name the whitespace
# ``str.strip`` (and so ``normalize_email``) also takes.
_ASCII_WHITESPACE = " \t\n\r\f\v"


def find_signed_in_user(
    db: Session, identity: AuthenticatedUser, *, move_email: bool = True
) -> User | None:
    """The persisted ``users`` row for this identity, or ``None``;
    never creates one (findings P5).

    **The principal id decides first.** The oldest row whose
    ``external_principal_id`` is the identity's Entra object id is the
    user, whatever email the claims now resolve to, so a pre-seeded
    invite for a new address cannot strand the account that holds the
    person's flags and session ownership. When that row's email
    differs from the resolved one (compared folded, as below) it takes
    the new email, stripped, audited as ``workspace.user_email_changed``
    — unless **another** row already holds that email, which would
    collide with the unique ``users.email``. That row is typically an
    invite pre-seeded for the new address, carrying newly granted flags
    or ownerships; when it has never been signed in to (``_absorbable``)
    it is folded in — flags OR'd, memberships moved, row deleted, email
    taken — audited as ``workspace.user_absorbed``. Otherwise the
    principal-id row keeps its email and a warning is logged.
    A missing or blank principal id never matches, and neither does a
    fake one: ``FAKE_AUTH_PRINCIPAL_ID`` is one constant slot shared by
    every ``FAKE_AUTH_EMAIL``, so matching on it would rename the
    developer's row whenever they switched identities.

    **Then the email.** Case-insensitive, trimmed on both sides: a
    pre-seeded row (``invite``) is reused regardless of casing, and a
    row stored padded before ``get_or_create_user`` stripped on write
    still finds its owner rather than gaining a duplicate (findings
    P3). The oldest match wins, so historical case-variant duplicates
    resolve deterministically rather than raising
    ``MultipleResultsFound``. An email match with no stored principal
    id records this one, under the same exclusions, so an invited row
    (``invite`` stores none) is found by principal id from then on.
    Not audited: the sign-in path's other writes to the row (its
    creation, ``_reassert_super_admin``) are not either. A non-empty
    stored principal id that differs is never overwritten: no row with
    this principal id exists (step one found none), and overwriting
    would take the row from the identity that recorded it.

    ``move_email=False`` writes nothing — no rename, no absorb, no recorded
    principal id — for a diagnostic page that must not sign anyone in
    (``/auth/me/debug``).
    """
    principal_id = identity.principal_id
    usable_principal = (
        not identity.is_fake
        and principal_id is not None
        and bool(principal_id.strip())
    )
    new_email = (identity.email or "").strip()

    if usable_principal:
        by_principal = db.execute(
            select(User)
            .where(User.external_principal_id == principal_id)
            .order_by(User.id)
            .limit(1)
        ).scalar_one_or_none()
        if by_principal is not None:
            if (
                move_email
                and new_email
                and normalize_email(by_principal.email) != normalize_email(new_email)
            ):
                _move_to_email(db, by_principal, new_email)
            return by_principal

    if not new_email:
        return None
    by_email = _by_email(db, new_email)
    if by_email is None:
        return None
    stored = by_email.external_principal_id
    if move_email and usable_principal and not (stored and stored.strip()):
        by_email.external_principal_id = principal_id
        db.commit()
        db.refresh(by_email)
    return by_email


def _by_email(
    db: Session, email: str, *, other_than: int | None = None
) -> User | None:
    stmt = select(User).where(
        func.lower(func.trim(User.email, _ASCII_WHITESPACE))
        == normalize_email(email)
    )
    if other_than is not None:
        stmt = stmt.where(User.id != other_than)
    return db.execute(stmt.order_by(User.id).limit(1)).scalar_one_or_none()


def _move_to_email(db: Session, target: User, new_email: str) -> None:
    holder = _by_email(db, new_email, other_than=target.id)
    if holder is None:
        _write_email_change(db, target, new_email)
    elif _absorbable(db, holder, target.external_principal_id):
        _absorb(db, target, holder, new_email)
    else:
        log.warning(
            "signed-in email held by another user row; not renamed",
            extra={"user_id": target.id, "holder_user_id": holder.id},
        )
        return
    db.commit()
    db.refresh(target)


def _absorbable(db: Session, holder: User, principal_id: str | None) -> bool:
    """Whether ``holder`` — the row already holding the signed-in
    identity's new email — can fold into the principal-id row: it
    carries no principal id of its own (or the same one), and nothing
    but flags and session memberships, so it has never been signed in
    to. Anything a sign-in leaves behind (an audit row it acted in, a
    session it created, a rehydrate stash, a data shape) refuses."""
    stored = (holder.external_principal_id or "").strip()
    if stored and holder.external_principal_id != principal_id:
        return False
    if _has_history(db, holder.id):
        return False
    for column in (RehydrateStash.operator_user_id, DataShape.created_by_user_id):
        if db.execute(select(column).where(column == holder.id).limit(1)).first():
            return False
    return True


def _absorb(db: Session, target: User, holder: User, new_email: str) -> None:
    """Fold ``holder`` into ``target`` in the caller's transaction: OR
    the two role flags, move the session memberships (a session both
    are on keeps ``target``'s), delete ``holder`` and give ``target``
    its email. One ``workspace.user_absorbed`` event names both ids."""
    old = {
        "email": target.email,
        "is_operator": target.is_operator,
        "is_sys_admin": target.is_sys_admin,
    }
    holder_id = holder.id
    target.is_operator = target.is_operator or holder.is_operator
    target.is_sys_admin = target.is_sys_admin or holder.is_sys_admin
    shared = select(SessionOperator.session_id).where(
        SessionOperator.user_id == target.id
    )
    db.execute(
        delete(SessionOperator)
        .where(SessionOperator.user_id == holder_id)
        .where(SessionOperator.session_id.in_(shared))
        .execution_options(synchronize_session=False)
    )
    moved = db.execute(
        update(SessionOperator)
        .where(SessionOperator.user_id == holder_id)
        .values(user_id=target.id)
        .execution_options(synchronize_session=False)
    ).rowcount
    # The memberships were moved in SQL; a collection loaded before
    # would make the delete cascade take them with the row.
    db.expire(holder, ["session_operators"])
    db.expire(target, ["session_operators"])
    db.delete(holder)
    # The unit of work flushes updates before deletes; the email is
    # unique, so the row holding it goes first.
    db.flush()
    target.email = new_email
    new = {
        "email": new_email,
        "is_operator": target.is_operator,
        "is_sys_admin": target.is_sys_admin,
    }
    audit.write_event(
        db,
        event_type="workspace.user_absorbed",
        summary=(
            f"Sign-in email changed from {old['email']} to {new_email}; "
            f"absorbed the row that held it"
        ),
        payload=audit.changes(
            {key: [old[key], new[key]] for key in old if old[key] != new[key]}
        ),
        refs={"target_user_id": target.id, "absorbed_user_id": holder_id},
        context={"memberships_moved": int(moved or 0)},
    )


def _write_email_change(db: Session, target: User, new_email: str) -> None:
    old = target.email
    target.email = new_email
    # No actor: the sign-in changed the row, not a person acting in
    # the app, so the row does not count as history (``_has_history``).
    audit.write_event(
        db,
        event_type="workspace.user_email_changed",
        summary=f"Sign-in email changed from {old} to {new_email}",
        payload=audit.changes({"email": [old, new_email]}),
        refs={"target_user_id": target.id},
    )


@dataclass(frozen=True)
class WorkspaceUserRow:
    id: int
    email: str
    display_name: str | None
    is_operator: bool
    is_sys_admin: bool
    is_super_admin: bool
    created_at: datetime
    session_operator_count: int
    sole_owner_count: int
    has_history: bool
    # The Accounts chip the row sits under (``account_listing.CATEGORIES``),
    # which decides its role controls (admin_pages_refine Item 2).
    category: str = ""


class UserOperationError(ValueError):
    """Raised when a workspace-role mutation violates an
    invariant. ``code`` is a stable machine identifier route
    handlers translate to HTTP status codes; ``message`` is the
    human-readable explanation. ``user_id`` is the row a batch refusal
    names (``apply_batch``), so the page can say which one."""

    def __init__(
        self, code: str, message: str, user_id: int | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.user_id = user_id


def _has_history(db: Session, user_id: int) -> bool:
    created = db.execute(
        select(ReviewSession.id)
        .where(ReviewSession.created_by_user_id == user_id)
        .limit(1)
    ).first()
    if created is not None:
        return True
    acted = db.execute(
        select(AuditEvent.id).where(AuditEvent.actor_user_id == user_id).limit(1)
    ).first()
    return acted is not None


def _guard_self(actor: User, target: User) -> None:
    if actor.id == target.id:
        raise UserOperationError(
            code="self_action",
            message=(
                "You can't change your own roles. Ask another sys-admin "
                "to flip your flags."
            ),
        )


def sys_admin_count(db: Session) -> int:
    """Every ``is_sys_admin`` row in the workspace: what the
    ``last_admin`` guard counts, so the page's Demote gate can ask the
    same question rather than counting the rows it happens to show."""
    return int(
        db.execute(
            select(func.count(User.id)).where(User.is_sys_admin.is_(True))
        ).scalar_one()
    )


def _guard_actor_super_admin(actor: User) -> None:
    """Segment 18S Item 1 — admin (``is_sys_admin``) promote / demote is
    **super-admin-only**, and so is inviting a new user as an admin. A
    plain sys-admin can no longer change who is an admin. Operator
    admit / revoke keeps requiring only admin.

    Item 2 — no-super-tier fallback. When **no** super-admin tier is
    configured (``SUPER_ADMIN_EMAILS`` empty, and no fake-auth fold-in),
    fall back to the pre-18S rule (any admin manages admins) rather than
    locking admin management out entirely — the strict rule engages only
    once a super-admin actually exists.
    """
    if not effective_super_admin_emails():
        return
    if not is_super_admin(actor.email):
        raise UserOperationError(
            code="requires_super_admin",
            message=(
                "Only a super-admin can grant, promote or demote admins. "
                "Ask a super-admin to change admin roles."
            ),
        )


def _guard_target_not_super_admin(target: User, action: str) -> None:
    """Segment 18S Item 1 — a super-admin is a protected account. No
    in-app path may demote / revoke / remove one, or strip it from its
    sessions; super-admin is set only via ``SUPER_ADMIN_EMAILS``
    (deployer config). Sits *above* the count-based ``last_admin`` floor
    — it protects a specific identity, not just a count."""
    if is_super_admin(target.email):
        raise UserOperationError(
            code="protected_super_admin",
            message=(
                f"{target.email} is a protected super-admin and can't be "
                f"{action}. Super-admin is granted only via the "
                "SUPER_ADMIN_EMAILS deployer config."
            ),
        )


def admit(
    db: Session,
    *,
    actor: User,
    target: User,
    correlation_id: str | None = None,
) -> None:
    _guard_self(actor, target)
    _write_admit(db, actor, target, correlation_id)
    db.commit()


def _write_admit(
    db: Session, actor: User, target: User, correlation_id: str | None
) -> None:
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
    # The batch's lock, before the owner count, so a concurrent owner
    # add (``session_owners.lock_owner_eligible``) either commits first
    # and is counted, or waits and sees the flag cleared.
    db.execute(_batch_lock("revoke", [target.id]))
    _guard_target_not_super_admin(target, "revoked")
    _guard_not_owner(db, target)
    _write_revoke(db, actor, target, correlation_id)
    db.commit()


def _owned_count(db: Session, target: User) -> int:
    return int(
        db.execute(
            select(func.count(SessionOperator.id)).where(
                SessionOperator.user_id == target.id
            )
        ).scalar_one()
    )


def _guard_not_owner(db: Session, target: User) -> None:
    owned = _owned_count(db, target)
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


def _guard_demote_not_owner(db: Session, target: User) -> None:
    """``still_owner`` for a Demote (findings P1): a sys-admin with no
    Operator flag is an operator only through the admin flag, so
    demoting one who owns a session would leave an owner who is no
    operator, as a Revoke would."""
    if target.is_operator:
        return
    owned = _owned_count(db, target)
    if owned > 0:
        raise UserOperationError(
            code="still_owner",
            message=(
                f"Refusing to demote {target.email} while they own "
                f"{owned} session{'s' if owned != 1 else ''}: without the "
                "Operator flag they would lose access to them. Admit them "
                "as an operator, or use 'Remove from all sessions', first."
            ),
        )


def _write_revoke(
    db: Session, actor: User, target: User, correlation_id: str | None
) -> None:
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


def promote(
    db: Session,
    *,
    actor: User,
    target: User,
    correlation_id: str | None = None,
) -> None:
    _guard_self(actor, target)
    _guard_actor_super_admin(actor)
    _write_promote(db, actor, target, correlation_id)
    db.commit()


def _write_promote(
    db: Session, actor: User, target: User, correlation_id: str | None
) -> None:
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


def demote(
    db: Session,
    *,
    actor: User,
    target: User,
    correlation_id: str | None = None,
) -> None:
    _guard_self(actor, target)
    _guard_actor_super_admin(actor)
    # Locked before the owner count, as ``revoke`` is, so a concurrent
    # owner add either commits first and is counted, or waits.
    db.execute(_batch_lock("demote", [target.id]))
    _guard_target_not_super_admin(target, "demoted")
    if sys_admin_count(db) <= 1 and target.is_sys_admin:
        raise UserOperationError(
            code="last_admin",
            message=(
                "Refusing to demote the only sys-admin in the workspace. "
                "Promote another user to sys-admin before demoting this one."
            ),
        )
    _guard_demote_not_owner(db, target)
    _write_demote(db, actor, target, correlation_id)
    db.commit()


def _write_demote(
    db: Session, actor: User, target: User, correlation_id: str | None
) -> None:
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
    _guard_target_not_super_admin(target, "removed from sessions")

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

    _write_detach(db, actor, target, rows, correlation_id)
    db.commit()
    return len(rows)


def _write_detach(
    db: Session,
    actor: User,
    target: User,
    rows: list[SessionOperator],
    correlation_id: str | None,
) -> None:
    deleted_session_ids = sorted(r.session_id for r in rows)
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
      more sessions (``session_operator_count > 0``).
    - ``has_history`` — refuses when the user created a session
      or acted in the audit log. Removal is for accounts with no
      activity (a mistyped invite, a sign-in that did nothing);
      access is taken away with Revoke, which keeps the row and
      so the attribution. Deleting the row does not keep anyone
      out: their next sign-in recreates it.

    On success the row is hard-deleted and a
    ``workspace.user_removed`` snapshot audit event records the
    last-known role state and the deleted email.
    """
    _guard_self(actor, target)
    _guard_target_not_super_admin(target, "removed")
    if target.is_sys_admin and sys_admin_count(db) <= 1:
        raise UserOperationError(
            code="last_admin",
            message=(
                "Refusing to remove the only sys-admin in the workspace. "
                "Promote another user to sys-admin before removing this one."
            ),
        )
    _guard_deletable(db, target)
    _write_remove(db, actor, target, correlation_id)
    db.commit()


def _guard_deletable(db: Session, target: User) -> None:
    owned = _owned_count(db, target)
    if owned > 0:
        raise UserOperationError(
            code="owns_sessions",
            message=(
                f"Refusing to remove {target.email} while they own "
                f"{owned} session{'s' if owned != 1 else ''}. "
                "To take their access away, remove them from all "
                "sessions and revoke them; removal is only for "
                "accounts with no activity."
            ),
        )
    if _has_history(db, target.id):
        raise UserOperationError(
            code="has_history",
            message=(
                f"Refusing to remove {target.email}: they have created "
                "sessions or have activity in the audit log, which "
                "keeps their name. Removal is only for accounts with no "
                "activity; to take an operator's access away, revoke it."
            ),
        )


def _write_remove(
    db: Session, actor: User, target: User, correlation_id: str | None
) -> None:
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


#: The actions the Accounts row expander applies to a selection
#: (admin_pages_refine Item 2), in the toolbar's order.
BATCH_ACTIONS: tuple[str, ...] = (
    "admit",
    "revoke",
    "remove_from_all_sessions",
    "promote",
    "demote",
    "delete",
)

_SUPER_ADMIN_VERBS = {
    "revoke": "revoked",
    "remove_from_all_sessions": "removed from sessions",
    "demote": "demoted",
    "delete": "removed",
}


def apply_batch(
    db: Session,
    *,
    actor: User,
    action: str,
    user_ids: list[int],
    correlation_id: str | None = None,
) -> int:
    """Apply one Accounts action to several rows, all or nothing.

    Each row takes the same guards its single-row action does, plus
    ``not_operator`` refusing Promote on a row with no role. The guards
    that count across rows judge the state **after** the batch, not one
    row at a time: ``last_admin`` refuses a Demote or Delete that would
    leave no sys-admin, however many admins it takes, and ``sole_owner``
    refuses a Remove from all sessions that would leave a session with
    no owner, however many of its co-owners are selected. What each
    counts is locked first, in id order (the sys-admin rows; the owner
    rows of every session the selection owns), so two batches can't
    both pass the count and both commit.

    The first refusal, in row-id order, refuses the batch and nothing
    changes. Otherwise every row is changed and audited as its
    single-row action would be, under one correlation id, and the
    number of rows is returned.
    """
    if action not in BATCH_ACTIONS:
        raise ValueError(f"unknown batch action {action!r}")
    ids = sorted(set(user_ids))
    if not ids:
        raise UserOperationError(
            code="empty_selection", message="Select at least one account."
        )
    if action in ("promote", "demote"):
        _guard_actor_super_admin(actor)

    # The admin count matters only to an action that can lower it, and
    # then every admin row is locked with the selection, in one id-ordered
    # statement so concurrent batches take the locks in the same order.
    # Only Delete removes rows, so only Delete takes the full lock; the
    # rest take FOR NO KEY UPDATE (the mode ``session_guard`` takes on its
    # session row), which an audit row's foreign-key check (FOR KEY SHARE
    # on its actor) doesn't wait on. With the full lock a bulk Remove
    # from all sessions and a concurrent ``session_owners.remove_owner``
    # by a selected user could deadlock: owner rows then user row against
    # user row then owners.
    counts_admins = action in ("demote", "delete")
    locked = list(db.execute(_batch_lock(action, ids)).scalars())
    by_id = {user.id: user for user in locked}
    missing = [user_id for user_id in ids if user_id not in by_id]
    if missing:
        raise UserOperationError(
            code="not_found",
            message=f"No account with id {missing[0]}.",
        )
    targets = [by_id[user_id] for user_id in ids]

    for target in targets:
        try:
            _guard_row(db, actor, action, target)
        except UserOperationError as exc:
            exc.user_id = target.id
            raise

    if counts_admins:
        _guard_admins_remain(action, locked, targets)

    detached: dict[int, list[SessionOperator]] = {}
    if action == "remove_from_all_sessions":
        detached = _lock_and_check_owners(db, targets)

    for target in targets:
        if action == "admit":
            _write_admit(db, actor, target, correlation_id)
        elif action == "revoke":
            _write_revoke(db, actor, target, correlation_id)
        elif action == "promote":
            _write_promote(db, actor, target, correlation_id)
        elif action == "demote":
            _write_demote(db, actor, target, correlation_id)
        elif action == "remove_from_all_sessions":
            # A row that owns nothing is a silent no-op, as on its own.
            if detached.get(target.id):
                _write_detach(db, actor, target, detached[target.id], correlation_id)
        else:
            _write_remove(db, actor, target, correlation_id)
    db.commit()
    return len(targets)


def _batch_lock(action: str, ids: list[int]) -> Select[tuple[User]]:
    """The selected rows, plus every sys-admin row when the action can
    lower the admin count, in id order. ``FOR NO KEY UPDATE`` except for
    Delete, which needs ``FOR UPDATE`` (see ``apply_batch``). The rows are
    re-read, so a guard never judges a copy loaded before the lock; that
    also discards any unflushed edit to them, so lock before editing."""
    rows = (
        or_(User.id.in_(ids), User.is_sys_admin.is_(True))
        if action in ("demote", "delete")
        else User.id.in_(ids)
    )
    return (
        select(User)
        .where(rows)
        .order_by(User.id)
        .with_for_update(key_share=action != "delete")
        .execution_options(populate_existing=True)
    )


def _guard_row(db: Session, actor: User, action: str, target: User) -> None:
    """The guards one row takes in a batch: its single-row action's,
    less the counts, which the batch judges as a whole."""
    _guard_self(actor, target)
    if action in _SUPER_ADMIN_VERBS:
        _guard_target_not_super_admin(target, _SUPER_ADMIN_VERBS[action])
    if action == "revoke":
        _guard_not_owner(db, target)
    elif action == "demote":
        _guard_demote_not_owner(db, target)
    elif action == "promote" and not (target.is_operator or target.is_sys_admin):
        raise UserOperationError(
            code="not_operator",
            message=(
                f"Refusing to promote {target.email}: they have no "
                "role. Admit them as an operator first."
            ),
        )
    elif action == "delete":
        _guard_deletable(db, target)


def _guard_admins_remain(
    action: str, locked: list[User], targets: list[User]
) -> None:
    """``last_admin`` on the state after the batch."""
    leaving = {target.id for target in targets if target.is_sys_admin}
    if not leaving:
        return
    remaining = [
        user for user in locked if user.is_sys_admin and user.id not in leaving
    ]
    if not remaining:
        verb = "demote" if action == "demote" else "remove"
        raise UserOperationError(
            user_id=min(leaving),
            code="last_admin",
            message=(
                f"Refusing to {verb} {len(leaving)} "
                f"sys-admin{'s' if len(leaving) != 1 else ''}: that would "
                "leave the workspace with none. Promote another user to "
                "sys-admin first."
            ),
        )


def _lock_and_check_owners(
    db: Session, targets: list[User]
) -> dict[int, list[SessionOperator]]:
    """``sole_owner`` on the state after the batch: lock the owner rows of
    every session a selected row owns, in id order, and refuse when a
    session would be left with no owner. Returns each target's own rows,
    for the write."""
    target_ids = {target.id for target in targets}
    session_ids = list(
        db.execute(
            select(SessionOperator.session_id)
            .where(SessionOperator.user_id.in_(target_ids))
            .distinct()
        ).scalars()
    )
    if not session_ids:
        return {}
    owner_rows = list(
        db.execute(
            select(SessionOperator)
            .where(SessionOperator.session_id.in_(session_ids))
            .order_by(SessionOperator.id)
            .with_for_update()
        ).scalars()
    )
    staying: set[int] = set()
    mine: dict[int, list[SessionOperator]] = {}
    for row in owner_rows:
        if row.user_id in target_ids:
            mine.setdefault(row.user_id, []).append(row)
        else:
            staying.add(row.session_id)
    orphaned = sorted(set(session_ids) - staying)
    if orphaned:
        by_id = {target.id: target for target in targets}
        first = min(
            row.user_id
            for rows in mine.values()
            for row in rows
            if row.session_id == orphaned[0]
        )
        raise UserOperationError(
            user_id=first,
            code="sole_owner",
            message=(
                f"Refusing to detach {by_id[first].email}: removing the "
                f"selected accounts would leave {len(orphaned)} "
                f"session{'s' if len(orphaned) != 1 else ''} with no owner. "
                "Add another owner to those sessions first."
            ),
        )
    return mine


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
    ``is_operator=True``, and inviting one grants the admin flag, so
    it takes the same super-admin guard as ``promote``."""
    email_normalised = email.strip()
    if not email_normalised or "@" not in email_normalised:
        raise UserOperationError(
            code="invalid_email",
            message=f"'{email}' is not a valid email address.",
        )
    existing = db.execute(
        select(User).where(
            func.lower(User.email) == normalize_email(email_normalised)
        )
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
        _guard_actor_super_admin(actor)
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
