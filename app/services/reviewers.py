"""Per-row CRUD for the ``reviewers`` table — Segment 15F PR 1.

Owns the create / update / bulk-status-flip surface the 15F
Setup-page UI lights up in PRs 2 + 3. The CSV importer in
``csv_imports.save_reviewers`` stays as the bulk wipe-and-replace
path; this module covers the single-row authoring + selection-
driven status flips per ``guide/segment_15F_enhanced_setup_pages.md``
decisions 12–13.

Every mutator wraps with ``lifecycle.invalidate_if_validated`` at
entry (the canonical Setup-mutation invariant from Segment 11A) and
emits the canonical audit envelope per Segment 11K.

Audit events registered in ``EVENT_SCHEMAS``:

- ``reviewer.created`` — snapshot envelope with the inserted row's
  fields.
- ``reviewer.updated`` — changes envelope, ``{field: [old, new]}``
  for every field the operator actually changed (no-op if nothing
  changed; nothing emitted).
- ``reviewer.bulk_inactivated`` / ``reviewer.bulk_reactivated`` —
  snapshot envelope listing the ids that were actually flipped
  (rows already at the target status are skipped silently).
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewer, ReviewSession, User
from app.services import audit
from app.services import session_lifecycle as lifecycle

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_VALID_STATUSES: frozenset[str] = frozenset({"active", "inactive"})


class ReviewerOperationError(ValueError):
    """Raised when a reviewer mutation violates an invariant.

    ``code`` is a stable machine identifier the route handler
    translates to an HTTP status; ``message`` is the
    human-readable explanation.

    Codes:
    - ``empty_name`` — name was empty / whitespace only.
    - ``invalid_email`` — email failed shape validation.
    - ``duplicate_email`` — another reviewer in the same session
      already uses this email (case-insensitive).
    - ``invalid_status`` — status not in ``{"active", "inactive"}``.
    - ``not_in_session`` — bulk operation referenced ids that don't
      belong to the target session.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _normalised_name(name: str) -> str:
    value = (name or "").strip()
    if not value:
        raise ReviewerOperationError("empty_name", "Name must not be empty.")
    return value


def _normalised_email(email: str) -> str:
    value = (email or "").strip()
    if not _EMAIL_RE.fullmatch(value):
        raise ReviewerOperationError(
            "invalid_email", f"{value!r} is not a valid email address."
        )
    return value


def _normalised_status(status: str) -> str:
    value = (status or "active").strip().lower()
    if value not in _VALID_STATUSES:
        raise ReviewerOperationError(
            "invalid_status",
            f"Status must be one of {sorted(_VALID_STATUSES)}; got {status!r}.",
        )
    return value


def _normalised_tag(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _email_taken(
    db: Session,
    *,
    session_id: int,
    email: str,
    exclude_reviewer_id: int | None = None,
) -> bool:
    stmt = select(Reviewer.id).where(
        Reviewer.session_id == session_id,
        Reviewer.email == email,
    )
    if exclude_reviewer_id is not None:
        stmt = stmt.where(Reviewer.id != exclude_reviewer_id)
    return db.execute(stmt).first() is not None


def create_reviewer(
    db: Session,
    *,
    review_session: ReviewSession,
    name: str,
    email: str,
    tag_1: str | None = None,
    tag_2: str | None = None,
    tag_3: str | None = None,
    status: str = "active",
    user: User,
    correlation_id: str | None = None,
) -> Reviewer:
    """Insert a new Reviewer row. Rejects duplicate emails within
    the session (case-sensitive match on the stored value). Returns
    the persisted row."""
    clean_name = _normalised_name(name)
    clean_email = _normalised_email(email)
    clean_status = _normalised_status(status)
    clean_tag_1 = _normalised_tag(tag_1)
    clean_tag_2 = _normalised_tag(tag_2)
    clean_tag_3 = _normalised_tag(tag_3)

    if _email_taken(db, session_id=review_session.id, email=clean_email):
        raise ReviewerOperationError(
            "duplicate_email",
            f"Another reviewer in this session already uses {clean_email!r}.",
        )

    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason="reviewer_created",
        correlation_id=correlation_id,
    )

    reviewer = Reviewer(
        session_id=review_session.id,
        name=clean_name,
        email=clean_email,
        status=clean_status,
        tag_1=clean_tag_1,
        tag_2=clean_tag_2,
        tag_3=clean_tag_3,
    )
    db.add(reviewer)
    db.flush()

    audit.write_event(
        db,
        event_type="reviewer.created",
        summary=f"Created reviewer {clean_email}",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.snapshot(
            {
                "reviewer_id": reviewer.id,
                "name": clean_name,
                "email": clean_email,
                "status": clean_status,
                "tag_1": clean_tag_1,
                "tag_2": clean_tag_2,
                "tag_3": clean_tag_3,
            }
        ),
        correlation_id=correlation_id,
    )
    db.commit()
    return reviewer


_UNSET: object = object()


def update_reviewer(
    db: Session,
    *,
    reviewer: Reviewer,
    name: str | object = _UNSET,
    email: str | object = _UNSET,
    tag_1: str | None | object = _UNSET,
    tag_2: str | None | object = _UNSET,
    tag_3: str | None | object = _UNSET,
    status: str | object = _UNSET,
    user: User,
    correlation_id: str | None = None,
) -> dict[str, list[object]]:
    """Field-level update. Only emits ``reviewer.updated`` if at
    least one field actually changed; the changes envelope carries
    ``{field: [old, new]}`` for each changed field only. Returns the
    changes dict (empty if nothing changed)."""
    proposed: dict[str, object] = {}
    if name is not _UNSET:
        proposed["name"] = _normalised_name(name)  # type: ignore[arg-type]
    if email is not _UNSET:
        proposed["email"] = _normalised_email(email)  # type: ignore[arg-type]
    if status is not _UNSET:
        proposed["status"] = _normalised_status(status)  # type: ignore[arg-type]
    if tag_1 is not _UNSET:
        proposed["tag_1"] = _normalised_tag(tag_1)  # type: ignore[arg-type]
    if tag_2 is not _UNSET:
        proposed["tag_2"] = _normalised_tag(tag_2)  # type: ignore[arg-type]
    if tag_3 is not _UNSET:
        proposed["tag_3"] = _normalised_tag(tag_3)  # type: ignore[arg-type]

    if "email" in proposed and proposed["email"] != reviewer.email:
        if _email_taken(
            db,
            session_id=reviewer.session_id,
            email=proposed["email"],  # type: ignore[arg-type]
            exclude_reviewer_id=reviewer.id,
        ):
            raise ReviewerOperationError(
                "duplicate_email",
                f"Another reviewer in this session already uses "
                f"{proposed['email']!r}.",
            )

    changes: dict[str, list[object]] = {}
    for field, new_value in proposed.items():
        old_value = getattr(reviewer, field)
        if old_value != new_value:
            changes[field] = [old_value, new_value]

    if not changes:
        return {}

    lifecycle.invalidate_if_validated(
        db,
        review_session=reviewer.session,
        user=user,
        reason="reviewer_updated",
        correlation_id=correlation_id,
    )

    for field, (_, new_value) in changes.items():
        setattr(reviewer, field, new_value)
    db.flush()

    # ``Assignment.is_self_review`` is keyed off ``reviewer.email``
    # (case-insensitive). If the email changed, every group this
    # reviewer is reviewing may need re-classification — recompute
    # against the whole session (the canonical helper handles the
    # whole-group rule for us).
    if "email" in changes:
        from app.services.assignments import (
            recompute_self_review_classification,
        )

        recompute_self_review_classification(
            db, session_id=reviewer.session_id
        )

    audit.write_event(
        db,
        event_type="reviewer.updated",
        summary=f"Updated reviewer {reviewer.email}",
        actor_user_id=user.id,
        session=reviewer.session,
        payload=audit.changes(changes),
        refs={"reviewer_id": reviewer.id},
        correlation_id=correlation_id,
    )
    db.commit()
    return changes


def _bulk_set_status(
    db: Session,
    *,
    review_session: ReviewSession,
    reviewer_ids: list[int],
    target_status: str,
    event_type: str,
    user: User,
    correlation_id: str | None,
) -> list[int]:
    """Shared implementation for bulk_inactivate / bulk_reactivate."""
    clean_target = _normalised_status(target_status)
    if not reviewer_ids:
        return []

    candidates = list(
        db.execute(
            select(Reviewer)
            .where(
                Reviewer.session_id == review_session.id,
                Reviewer.id.in_(reviewer_ids),
            )
            .order_by(Reviewer.id)
        ).scalars()
    )
    found_ids = {r.id for r in candidates}
    missing = set(reviewer_ids) - found_ids
    if missing:
        raise ReviewerOperationError(
            "not_in_session",
            f"Reviewer ids {sorted(missing)} do not belong to "
            f"session {review_session.id}.",
        )

    flipped = [r for r in candidates if r.status != clean_target]
    if not flipped:
        return []

    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason="reviewer_bulk_status_change",
        correlation_id=correlation_id,
    )

    flipped_ids = [r.id for r in flipped]
    for r in flipped:
        r.status = clean_target
    db.flush()

    audit.write_event(
        db,
        event_type=event_type,
        summary=(
            f"Flipped {len(flipped_ids)} reviewer"
            f"{'' if len(flipped_ids) == 1 else 's'} → {clean_target}"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.snapshot({"reviewer_ids": flipped_ids}),
        correlation_id=correlation_id,
    )
    db.commit()
    return flipped_ids


def bulk_inactivate(
    db: Session,
    *,
    review_session: ReviewSession,
    reviewer_ids: list[int],
    user: User,
    correlation_id: str | None = None,
) -> list[int]:
    """Flip ``status="inactive"`` on every reviewer in ``reviewer_ids``
    that isn't already inactive. Returns the ids actually flipped.
    Rows already inactive are skipped silently."""
    return _bulk_set_status(
        db,
        review_session=review_session,
        reviewer_ids=reviewer_ids,
        target_status="inactive",
        event_type="reviewer.bulk_inactivated",
        user=user,
        correlation_id=correlation_id,
    )


def bulk_reactivate(
    db: Session,
    *,
    review_session: ReviewSession,
    reviewer_ids: list[int],
    user: User,
    correlation_id: str | None = None,
) -> list[int]:
    """Flip ``status="active"`` on every reviewer in ``reviewer_ids``
    that isn't already active. Returns the ids actually flipped.
    Rows already active are skipped silently."""
    return _bulk_set_status(
        db,
        review_session=review_session,
        reviewer_ids=reviewer_ids,
        target_status="active",
        event_type="reviewer.bulk_reactivated",
        user=user,
        correlation_id=correlation_id,
    )


__all__ = [
    "ReviewerOperationError",
    "create_reviewer",
    "update_reviewer",
    "bulk_inactivate",
    "bulk_reactivate",
]
