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

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionOperator, User
from app.services import audit
from app.services.email_identity import normalize_email


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


def _workspace_operators(db: Session) -> list[User]:
    """Everyone ``add_owner`` would accept: operators and sys-admins."""
    return list(
        db.execute(
            select(User)
            .where((User.is_operator.is_(True)) | (User.is_sys_admin.is_(True)))
            .order_by(User.email.asc())
        ).scalars()
    )


def session_owner_candidates(db: Session) -> list[User]:
    """The Add-owner picker's candidates on Session Home (19S Item 10).

    **Every** workspace operator, current owners included (author's
    ruling, 2026-09-23): owners are staged, so one removed in the table
    can be picked again before Save. The stager already ignores an
    address that is in the table.
    """
    return _workspace_operators(db)


def new_session_owner_candidates(db: Session, creator: User) -> list[User]:
    """The Add-owner picker's candidates on the Create page (19S Item 9).

    There is no session yet, so no owner list to exclude — only the
    creator, who becomes the first owner the moment the session exists.
    """
    return [u for u in _workspace_operators(db) if u.id != creator.id]


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
    row = _insert_owner(
        db,
        review_session=review_session,
        actor=actor,
        target=target,
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(row)
    return row


def _insert_owner(
    db: Session,
    *,
    review_session: ReviewSession,
    actor: User,
    target: User,
    correlation_id: str | None,
) -> SessionOperator:
    """Insert the owner row and its audit event; the caller commits."""
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
    locked_rows = _lock_owner_rows(db, review_session)
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
    _delete_owner(
        db,
        review_session=review_session,
        actor=actor,
        target=target,
        row=target_row,
        correlation_id=correlation_id,
    )
    db.commit()


def _lock_owner_rows(
    db: Session, review_session: ReviewSession
) -> list[SessionOperator]:
    """The session's owner rows, locked ``FOR UPDATE`` (see ``remove_owner``).

    In ``id`` order, so two lockers take the row locks in the same order
    and cannot deadlock each other."""
    return list(
        db.execute(
            select(SessionOperator)
            .where(SessionOperator.session_id == review_session.id)
            .order_by(SessionOperator.id)
            .with_for_update()
        ).scalars()
    )


def _delete_owner(
    db: Session,
    *,
    review_session: ReviewSession,
    actor: User,
    target: User,
    row: SessionOperator,
    correlation_id: str | None,
) -> None:
    """Delete the owner row and write its audit event; the caller commits."""
    db.delete(row)
    db.flush()
    audit.write_event(
        db,
        event_type="session.owner_removed",
        summary=f"Removed {target.email} as owner of session {review_session.code}",
        actor_user_id=actor.id,
        session=review_session,
        payload=audit.snapshot(
            {"user_id": target.id, "email": target.email, "role": row.role}
        ),
        refs={"target_user_id": target.id},
        correlation_id=correlation_id,
    )


def resolve_owners(db: Session, emails: list[str]) -> list[User]:
    """Validate a desired owner list before anything is written.

    19S Item 9 (Create) and Item 10 (Session Home) stage owner rows in a
    form and save them with the page, so the whole list is checked up
    front: one bad email must refuse the save, not land half of it.
    Blank entries are skipped, case is folded and duplicates collapse,
    in the order given. Every email must be a user ``add_owner`` would
    accept — a workspace operator or sys-admin — or the call raises
    ``not_in_workspace`` naming it. An empty result is returned as-is;
    ``set_owners`` refuses it.
    """
    resolved: list[User] = []
    seen: set[int] = set()
    for raw in emails:
        if not raw or not raw.strip():
            continue
        email = normalize_email(raw)
        target = db.execute(
            select(User).where(func.lower(User.email) == email)
        ).scalar_one_or_none()
        if target is None or not (target.is_operator or target.is_sys_admin):
            raise OwnerOperationError(
                code="not_in_workspace",
                message=(
                    f"{raw.strip()} is not on the workspace operator "
                    "allowlist. Admit them via the Admin → Accounts "
                    "Management page first."
                ),
            )
        if target.id not in seen:
            seen.add(target.id)
            resolved.append(target)
    return resolved


def apply_owner_changes(
    db: Session,
    *,
    review_session: ReviewSession,
    actor: User,
    original: list[str],
    wanted: list[str],
    correlation_id: str | None = None,
) -> None:
    """Save Session Home's Owners card **as changes**, in one transaction.

    The card posts the owners it was rendered with (``original``) beside
    the ones its table holds now (``wanted``). Only the difference is
    applied (19S Item 10, author's ruling 2026-09-23): addresses added in
    the table are added, addresses removed from it are removed, and every
    other owner is left as the session has it **now** — so a page left
    open while another owner saved neither drops the owner they added
    nor restores one they removed, and an untouched table changes no one.

    The delta is applied to the owner rows **locked at write time**, not
    resolved into a whole set beforehand, so a save committed before this
    one takes its lock is not overwritten, and an addition or removal it
    already made is simply satisfied. Under Postgres's READ COMMITTED a
    save committing *while* this one waits on the lock can still make it
    refuse — a duplicate insert, or ``last_owner`` counting without the
    other's additions — but never break the one-owner rule.
    Only the additions are validated (``resolve_owners``), so an owner
    who has since lost operator status blocks nothing.

    **All or nothing**: the adds, removes and their audit events share
    one commit, and any refusal rolls every one of them back — a
    non-operator address, a result with no owner left (``last_owner``),
    or a clash with a concurrent save (``owners_changed``).
    """

    def _normalized(emails: list[str]) -> list[str]:
        seen: list[str] = []
        for raw in emails:
            if raw and raw.strip():
                email = normalize_email(raw)
                if email not in seen:
                    seen.append(email)
        return seen

    before = _normalized(original)
    after = _normalized(wanted)
    additions = resolve_owners(db, [email for email in after if email not in before])
    removals = {email for email in before if email not in after}
    try:
        rows = {row.user_id: row for row in _lock_owner_rows(db, review_session)}
        for target in additions:
            if target.id not in rows:
                rows[target.id] = _insert_owner(
                    db,
                    review_session=review_session,
                    actor=actor,
                    target=target,
                    correlation_id=correlation_id,
                )
        for user_id, row in list(rows.items()):
            target = db.get(User, user_id)
            if normalize_email(target.email) in removals:
                _delete_owner(
                    db,
                    review_session=review_session,
                    actor=actor,
                    target=target,
                    row=row,
                    correlation_id=correlation_id,
                )
                del rows[user_id]
        if not rows:
            raise OwnerOperationError(
                code="last_owner",
                message="A session always keeps at least one owner.",
            )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise OwnerOperationError(
            code="owners_changed",
            message="Another save changed this session's owners at the same time.",
        ) from exc
    except OwnerOperationError:
        db.rollback()
        raise


def set_owners(
    db: Session,
    *,
    review_session: ReviewSession,
    actor: User,
    targets: list[User],
    correlation_id: str | None = None,
) -> tuple[list[User], list[User]]:
    """Replace a session's owner set with ``targets``; return (added, removed).

    The owners counterpart of ``session_tags.set_tags``. It **adds before
    it removes**, so the set never passes through zero and
    ``remove_owner``'s last-owner guard is never the thing that stops a
    valid replacement. An empty ``targets`` is refused outright — a
    session always keeps one owner. Each change goes through
    ``add_owner`` / ``remove_owner``, so the audit events, the lock and
    the invariants are theirs; a target already an owner, or an owner
    kept, emits nothing. Validate the list with ``resolve_owners`` (Create)
    first. Session Home's card saves changes instead, through
    ``apply_owner_changes``.
    """
    if not targets:
        raise OwnerOperationError(
            code="last_owner",
            message="A session always keeps at least one owner.",
        )
    # A target listed twice would otherwise be added twice: the first
    # ``add_owner`` commits, the second raises ``already_owner`` — a
    # partial write (Item 9 close, cold read L1).
    unique: dict[int, User] = {}
    for target in targets:
        unique.setdefault(target.id, target)
    targets = list(unique.values())
    current = {row.user_id for row in list_owners(db, review_session)}
    wanted = {target.id for target in targets}
    added: list[User] = []
    for target in targets:
        if target.id not in current:
            add_owner(
                db,
                review_session=review_session,
                actor=actor,
                target=target,
                correlation_id=correlation_id,
            )
            added.append(target)
    removed: list[User] = []
    for user_id in sorted(current - wanted):
        target = db.get(User, user_id)
        remove_owner(
            db,
            review_session=review_session,
            actor=actor,
            target=target,
            correlation_id=correlation_id,
        )
        removed.append(target)
    return added, removed
