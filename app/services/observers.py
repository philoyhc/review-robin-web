"""Per-row CRUD for the ``observers`` table.

Mirrors ``app.services.reviewers`` for the observer roster — the
third participant audience landed inert in Phase 1
(``guide/archive/participant_model_upgrade.md``). The Setup-Observers page
lights up via these helpers; the CSV importer in
``csv_imports.save_observers`` covers the bulk wipe-and-replace
path.

Observers have a simpler shape than reviewers: ``email`` is the
auth-bearing identity (required + unique per session),
``display_name`` is an optional human-facing label, and a single
``tag_1`` (not three) is the only categorical axis.

Audit events registered in ``EVENT_SCHEMAS``:

- ``observer.created`` — snapshot envelope with the inserted row's
  fields.
- ``observer.updated`` — changes envelope, ``{field: [old, new]}``
  for every field the operator actually changed (no-op if nothing
  changed; nothing emitted).
- ``observer.bulk_inactivated`` / ``observer.bulk_reactivated`` —
  snapshot envelope listing the ids that were actually flipped
  (rows already at the target status are skipped silently).
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, ReviewSession, User
from app.services import audit
from app.services import session_lifecycle as lifecycle

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_VALID_STATUSES: frozenset[str] = frozenset({"active", "inactive"})


class ObserverOperationError(ValueError):
    """Raised when an observer mutation violates an invariant.

    Codes:
    - ``invalid_email`` — email failed shape validation.
    - ``duplicate_email`` — another observer in the same session
      already uses this email (case-insensitive).
    - ``invalid_status`` — status not in ``{"active", "inactive"}``.
    - ``not_in_session`` — bulk operation referenced ids that don't
      belong to the target session.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _normalised_email(email: str) -> str:
    value = (email or "").strip()
    if not _EMAIL_RE.fullmatch(value):
        raise ObserverOperationError(
            "invalid_email", f"{value!r} is not a valid email address."
        )
    return value


def _normalised_status(status: str) -> str:
    value = (status or "active").strip().lower()
    if value not in _VALID_STATUSES:
        raise ObserverOperationError(
            "invalid_status",
            f"Status must be one of {sorted(_VALID_STATUSES)}; got {status!r}.",
        )
    return value


def _normalised_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _email_taken(
    db: Session,
    *,
    session_id: int,
    email: str,
    exclude_observer_id: int | None = None,
) -> bool:
    stmt = select(Observer.id).where(
        Observer.session_id == session_id,
        Observer.email == email,
    )
    if exclude_observer_id is not None:
        stmt = stmt.where(Observer.id != exclude_observer_id)
    return db.execute(stmt).first() is not None


def create_observer(
    db: Session,
    *,
    review_session: ReviewSession,
    email: str,
    display_name: str | None = None,
    tag_1: str | None = None,
    status: str = "active",
    user: User,
    correlation_id: str | None = None,
) -> Observer:
    """Insert a new Observer row. Rejects duplicate emails within
    the session. Returns the persisted row."""
    clean_email = _normalised_email(email)
    clean_status = _normalised_status(status)
    clean_display_name = _normalised_optional(display_name)
    clean_tag_1 = _normalised_optional(tag_1)

    if _email_taken(db, session_id=review_session.id, email=clean_email):
        raise ObserverOperationError(
            "duplicate_email",
            f"Another observer in this session already uses {clean_email!r}.",
        )

    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason="observer_created",
        correlation_id=correlation_id,
    )

    observer = Observer(
        session_id=review_session.id,
        email=clean_email,
        display_name=clean_display_name,
        status=clean_status,
        tag_1=clean_tag_1,
    )
    db.add(observer)
    db.flush()

    audit.write_event(
        db,
        event_type="observer.created",
        summary=f"Created observer {clean_email}",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.snapshot(
            {
                "observer_id": observer.id,
                "email": clean_email,
                "display_name": clean_display_name,
                "status": clean_status,
                "tag_1": clean_tag_1,
            }
        ),
        correlation_id=correlation_id,
    )
    db.commit()
    return observer


_UNSET: object = object()


def update_observer(
    db: Session,
    *,
    observer: Observer,
    email: str | object = _UNSET,
    display_name: str | None | object = _UNSET,
    tag_1: str | None | object = _UNSET,
    status: str | object = _UNSET,
    user: User,
    correlation_id: str | None = None,
) -> dict[str, list[object]]:
    """Field-level update. Only emits ``observer.updated`` if at
    least one field actually changed; the changes envelope carries
    ``{field: [old, new]}`` for each changed field only. Returns
    the changes dict (empty if nothing changed)."""
    proposed: dict[str, object] = {}
    if email is not _UNSET:
        proposed["email"] = _normalised_email(email)  # type: ignore[arg-type]
    if status is not _UNSET:
        proposed["status"] = _normalised_status(status)  # type: ignore[arg-type]
    if display_name is not _UNSET:
        proposed["display_name"] = _normalised_optional(display_name)  # type: ignore[arg-type]
    if tag_1 is not _UNSET:
        proposed["tag_1"] = _normalised_optional(tag_1)  # type: ignore[arg-type]

    if "email" in proposed and proposed["email"] != observer.email:
        if _email_taken(
            db,
            session_id=observer.session_id,
            email=proposed["email"],  # type: ignore[arg-type]
            exclude_observer_id=observer.id,
        ):
            raise ObserverOperationError(
                "duplicate_email",
                f"Another observer in this session already uses "
                f"{proposed['email']!r}.",
            )

    changes: dict[str, list[object]] = {}
    for field, new_value in proposed.items():
        old_value = getattr(observer, field)
        if old_value != new_value:
            changes[field] = [old_value, new_value]

    if not changes:
        return {}

    lifecycle.invalidate_if_validated(
        db,
        review_session=observer.session,
        user=user,
        reason="observer_updated",
        correlation_id=correlation_id,
    )

    for field, (_, new_value) in changes.items():
        setattr(observer, field, new_value)
    db.flush()

    audit.write_event(
        db,
        event_type="observer.updated",
        summary=f"Updated observer {observer.email}",
        actor_user_id=user.id,
        session=observer.session,
        payload=audit.changes(changes),
        refs={"observer_id": observer.id},
        correlation_id=correlation_id,
    )
    db.commit()
    return changes


def _bulk_set_status(
    db: Session,
    *,
    review_session: ReviewSession,
    observer_ids: list[int],
    target_status: str,
    event_type: str,
    user: User,
    correlation_id: str | None,
) -> list[int]:
    """Shared implementation for bulk_inactivate / bulk_reactivate."""
    clean_target = _normalised_status(target_status)
    if not observer_ids:
        return []

    candidates = list(
        db.execute(
            select(Observer)
            .where(
                Observer.session_id == review_session.id,
                Observer.id.in_(observer_ids),
            )
            .order_by(Observer.id)
        ).scalars()
    )
    found_ids = {o.id for o in candidates}
    missing = set(observer_ids) - found_ids
    if missing:
        raise ObserverOperationError(
            "not_in_session",
            f"Observer ids {sorted(missing)} do not belong to "
            f"session {review_session.id}.",
        )

    flipped = [o for o in candidates if o.status != clean_target]
    if not flipped:
        return []

    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason="observer_bulk_status_change",
        correlation_id=correlation_id,
    )

    flipped_ids = [o.id for o in flipped]
    for o in flipped:
        o.status = clean_target
    db.flush()

    audit.write_event(
        db,
        event_type=event_type,
        summary=(
            f"Flipped {len(flipped_ids)} observer"
            f"{'' if len(flipped_ids) == 1 else 's'} → {clean_target}"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.snapshot({"observer_ids": flipped_ids}),
        correlation_id=correlation_id,
    )
    db.commit()
    return flipped_ids


def bulk_inactivate(
    db: Session,
    *,
    review_session: ReviewSession,
    observer_ids: list[int],
    user: User,
    correlation_id: str | None = None,
) -> list[int]:
    """Flip ``status="inactive"`` on every observer in ``observer_ids``
    that isn't already inactive. Returns the ids actually flipped."""
    return _bulk_set_status(
        db,
        review_session=review_session,
        observer_ids=observer_ids,
        target_status="inactive",
        event_type="observer.bulk_inactivated",
        user=user,
        correlation_id=correlation_id,
    )


def bulk_reactivate(
    db: Session,
    *,
    review_session: ReviewSession,
    observer_ids: list[int],
    user: User,
    correlation_id: str | None = None,
) -> list[int]:
    """Flip ``status="active"`` on every observer in ``observer_ids``
    that isn't already active. Returns the ids actually flipped."""
    return _bulk_set_status(
        db,
        review_session=review_session,
        observer_ids=observer_ids,
        target_status="active",
        event_type="observer.bulk_reactivated",
        user=user,
        correlation_id=correlation_id,
    )


__all__ = [
    "ObserverOperationError",
    "create_observer",
    "update_observer",
    "bulk_inactivate",
    "bulk_reactivate",
]
