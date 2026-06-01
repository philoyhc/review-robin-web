"""Per-row CRUD for the ``reviewees`` table — Segment 15F PR 4.

The reviewee-side mirror of ``app/services/reviewers.py``. Owns the
create / update / bulk-status-flip surface the 15F Reviewees Setup
page lights up. The CSV importer in ``csv_imports.save_reviewees``
stays as the bulk wipe-and-replace path.

Unlike reviewers, the identity column is ``email_or_identifier``
and is validated non-strict — a non-email handle (no ``@``) is
accepted, but a value containing ``@`` must still be a well-formed
email so typos surface here rather than at send time. This matches
``csv_imports._parse_email(strict=False)``.

Audit events registered in ``EVENT_SCHEMAS``:

- ``reviewee.created`` — snapshot envelope.
- ``reviewee.updated`` — changes envelope, changed fields only.
- ``reviewee.bulk_inactivated`` / ``reviewee.bulk_reactivated`` —
  snapshot envelope listing the flipped ids.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, ReviewSession, User
from app.services import audit
from app.services import session_lifecycle as lifecycle

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_VALID_STATUSES: frozenset[str] = frozenset({"active", "inactive"})


class RevieweeOperationError(ValueError):
    """Raised when a reviewee mutation violates an invariant.

    ``code`` is a stable machine identifier the route handler
    translates to an HTTP status; ``message`` is the
    human-readable explanation.

    Codes:
    - ``empty_name`` — name was empty / whitespace only.
    - ``empty_identifier`` — email-or-identifier was empty.
    - ``invalid_email`` — an ``@``-bearing identifier failed
      email-shape validation.
    - ``duplicate_identifier`` — another reviewee in the same
      session already uses this email-or-identifier.
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
        raise RevieweeOperationError("empty_name", "Name must not be empty.")
    return value


def _normalised_identifier(identifier: str) -> str:
    value = (identifier or "").strip()
    if not value:
        raise RevieweeOperationError(
            "empty_identifier", "Email / identifier must not be empty."
        )
    # Non-strict: a handle without ``@`` is fine; anything with an
    # ``@`` must be a well-formed email.
    if "@" in value and not _EMAIL_RE.fullmatch(value):
        raise RevieweeOperationError(
            "invalid_email", f"{value!r} is not a valid email address."
        )
    return value


def _normalised_status(status: str) -> str:
    value = (status or "active").strip().lower()
    if value not in _VALID_STATUSES:
        raise RevieweeOperationError(
            "invalid_status",
            f"Status must be one of {sorted(_VALID_STATUSES)}; got {status!r}.",
        )
    return value


def _normalised_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _identifier_taken(
    db: Session,
    *,
    session_id: int,
    identifier: str,
    exclude_reviewee_id: int | None = None,
) -> bool:
    stmt = select(Reviewee.id).where(
        Reviewee.session_id == session_id,
        Reviewee.email_or_identifier == identifier,
    )
    if exclude_reviewee_id is not None:
        stmt = stmt.where(Reviewee.id != exclude_reviewee_id)
    return db.execute(stmt).first() is not None


def create_reviewee(
    db: Session,
    *,
    review_session: ReviewSession,
    name: str,
    email_or_identifier: str,
    profile_link: str | None = None,
    tag_1: str | None = None,
    tag_2: str | None = None,
    tag_3: str | None = None,
    status: str = "active",
    user: User,
    correlation_id: str | None = None,
) -> Reviewee:
    """Insert a new Reviewee row. Rejects a duplicate
    email-or-identifier within the session. Returns the persisted
    row."""
    clean_name = _normalised_name(name)
    clean_identifier = _normalised_identifier(email_or_identifier)
    clean_status = _normalised_status(status)
    clean_profile_link = _normalised_optional(profile_link)
    clean_tag_1 = _normalised_optional(tag_1)
    clean_tag_2 = _normalised_optional(tag_2)
    clean_tag_3 = _normalised_optional(tag_3)

    if _identifier_taken(
        db, session_id=review_session.id, identifier=clean_identifier
    ):
        raise RevieweeOperationError(
            "duplicate_identifier",
            f"Another reviewee in this session already uses "
            f"{clean_identifier!r}.",
        )

    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason="reviewee_created",
        correlation_id=correlation_id,
    )

    reviewee = Reviewee(
        session_id=review_session.id,
        name=clean_name,
        email_or_identifier=clean_identifier,
        profile_link=clean_profile_link,
        status=clean_status,
        tag_1=clean_tag_1,
        tag_2=clean_tag_2,
        tag_3=clean_tag_3,
    )
    db.add(reviewee)
    db.flush()

    audit.write_event(
        db,
        event_type="reviewee.created",
        summary=f"Created reviewee {clean_identifier}",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.snapshot(
            {
                "reviewee_id": reviewee.id,
                "name": clean_name,
                "email_or_identifier": clean_identifier,
                "profile_link": clean_profile_link,
                "status": clean_status,
                "tag_1": clean_tag_1,
                "tag_2": clean_tag_2,
                "tag_3": clean_tag_3,
            }
        ),
        correlation_id=correlation_id,
    )
    db.commit()
    return reviewee


_UNSET: object = object()


def update_reviewee(
    db: Session,
    *,
    reviewee: Reviewee,
    name: str | object = _UNSET,
    email_or_identifier: str | object = _UNSET,
    profile_link: str | None | object = _UNSET,
    tag_1: str | None | object = _UNSET,
    tag_2: str | None | object = _UNSET,
    tag_3: str | None | object = _UNSET,
    status: str | object = _UNSET,
    user: User,
    correlation_id: str | None = None,
) -> dict[str, list[object]]:
    """Field-level update. Only emits ``reviewee.updated`` if at
    least one field actually changed; the changes envelope carries
    ``{field: [old, new]}`` for each changed field only. Returns the
    changes dict (empty if nothing changed)."""
    proposed: dict[str, object] = {}
    if name is not _UNSET:
        proposed["name"] = _normalised_name(name)  # type: ignore[arg-type]
    if email_or_identifier is not _UNSET:
        proposed["email_or_identifier"] = _normalised_identifier(
            email_or_identifier  # type: ignore[arg-type]
        )
    if status is not _UNSET:
        proposed["status"] = _normalised_status(status)  # type: ignore[arg-type]
    if profile_link is not _UNSET:
        proposed["profile_link"] = _normalised_optional(
            profile_link  # type: ignore[arg-type]
        )
    if tag_1 is not _UNSET:
        proposed["tag_1"] = _normalised_optional(tag_1)  # type: ignore[arg-type]
    if tag_2 is not _UNSET:
        proposed["tag_2"] = _normalised_optional(tag_2)  # type: ignore[arg-type]
    if tag_3 is not _UNSET:
        proposed["tag_3"] = _normalised_optional(tag_3)  # type: ignore[arg-type]

    if (
        "email_or_identifier" in proposed
        and proposed["email_or_identifier"] != reviewee.email_or_identifier
    ):
        if _identifier_taken(
            db,
            session_id=reviewee.session_id,
            identifier=proposed["email_or_identifier"],  # type: ignore[arg-type]
            exclude_reviewee_id=reviewee.id,
        ):
            raise RevieweeOperationError(
                "duplicate_identifier",
                f"Another reviewee in this session already uses "
                f"{proposed['email_or_identifier']!r}.",
            )

    changes: dict[str, list[object]] = {}
    for field, new_value in proposed.items():
        old_value = getattr(reviewee, field)
        if old_value != new_value:
            changes[field] = [old_value, new_value]

    if not changes:
        return {}

    lifecycle.invalidate_if_validated(
        db,
        review_session=reviewee.session,
        user=user,
        reason="reviewee_updated",
        correlation_id=correlation_id,
    )

    for field, (_, new_value) in changes.items():
        setattr(reviewee, field, new_value)
    db.flush()

    # A grouping-tag change moves this reviewee between groups: its
    # mis-attributed fanned answer copies are deleted, and the
    # assignment is re-fanned from its new group so a relocated
    # reviewee surfaces that group's answer rather than a blank row
    # (Segment 13C PR 5; re-fan Segment 18H). No-op unless a
    # changed tag is a group boundary.
    from app.services import responses as responses_service

    defuncted = responses_service.reconcile_group_responses_for_tag_change(
        db,
        reviewee=reviewee,
        changed_tag_fields={
            f for f in changes if f in ("tag_1", "tag_2", "tag_3")
        },
    )

    # ``Assignment.is_self_review`` is keyed off
    # ``reviewee.email_or_identifier`` (via the canonical helper)
    # AND off the reviewee's boundary tags (via the whole-group
    # rule). Either kind of change can shift the classification —
    # recompute against the whole session if any of those fields
    # moved.
    if any(
        f in changes
        for f in ("email_or_identifier", "tag_1", "tag_2", "tag_3")
    ):
        from app.services.assignments import (
            recompute_self_review_classification,
        )

        recompute_self_review_classification(
            db, session_id=reviewee.session_id
        )

    audit.write_event(
        db,
        event_type="reviewee.updated",
        summary=f"Updated reviewee {reviewee.email_or_identifier}",
        actor_user_id=user.id,
        session=reviewee.session,
        payload=audit.changes(changes),
        refs={"reviewee_id": reviewee.id},
        context=(
            {"defuncted_group_responses": defuncted} if defuncted else None
        ),
        correlation_id=correlation_id,
    )
    db.commit()
    return changes


def _bulk_set_status(
    db: Session,
    *,
    review_session: ReviewSession,
    reviewee_ids: list[int],
    target_status: str,
    event_type: str,
    user: User,
    correlation_id: str | None,
) -> list[int]:
    """Shared implementation for bulk_inactivate / bulk_reactivate."""
    clean_target = _normalised_status(target_status)
    if not reviewee_ids:
        return []

    candidates = list(
        db.execute(
            select(Reviewee)
            .where(
                Reviewee.session_id == review_session.id,
                Reviewee.id.in_(reviewee_ids),
            )
            .order_by(Reviewee.id)
        ).scalars()
    )
    found_ids = {r.id for r in candidates}
    missing = set(reviewee_ids) - found_ids
    if missing:
        raise RevieweeOperationError(
            "not_in_session",
            f"Reviewee ids {sorted(missing)} do not belong to "
            f"session {review_session.id}.",
        )

    flipped = [r for r in candidates if r.status != clean_target]
    if not flipped:
        return []

    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason="reviewee_bulk_status_change",
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
            f"Flipped {len(flipped_ids)} reviewee"
            f"{'' if len(flipped_ids) == 1 else 's'} → {clean_target}"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.snapshot({"reviewee_ids": flipped_ids}),
        correlation_id=correlation_id,
    )
    db.commit()
    return flipped_ids


def bulk_inactivate(
    db: Session,
    *,
    review_session: ReviewSession,
    reviewee_ids: list[int],
    user: User,
    correlation_id: str | None = None,
) -> list[int]:
    """Flip ``status="inactive"`` on every reviewee in
    ``reviewee_ids`` that isn't already inactive. Returns the ids
    actually flipped."""
    return _bulk_set_status(
        db,
        review_session=review_session,
        reviewee_ids=reviewee_ids,
        target_status="inactive",
        event_type="reviewee.bulk_inactivated",
        user=user,
        correlation_id=correlation_id,
    )


def bulk_reactivate(
    db: Session,
    *,
    review_session: ReviewSession,
    reviewee_ids: list[int],
    user: User,
    correlation_id: str | None = None,
) -> list[int]:
    """Flip ``status="active"`` on every reviewee in
    ``reviewee_ids`` that isn't already active. Returns the ids
    actually flipped."""
    return _bulk_set_status(
        db,
        review_session=review_session,
        reviewee_ids=reviewee_ids,
        target_status="active",
        event_type="reviewee.bulk_reactivated",
        user=user,
        correlation_id=correlation_id,
    )


def acknowledge_results(
    db: Session,
    *,
    review_session: ReviewSession,
    reviewee: Reviewee,
    user: User,
    correlation_id: str | None = None,
) -> bool:
    """Stamp ``reviewee.results_acknowledged_at`` with the current
    UTC time and emit a ``reviewee.results_acknowledged`` audit
    event. Returns ``True`` if a new stamp was written, ``False``
    if the reviewee had already acknowledged (idempotent — once
    acknowledged, stays acknowledged)."""
    if reviewee.results_acknowledged_at is not None:
        return False
    now = datetime.now(timezone.utc)
    reviewee.results_acknowledged_at = now
    db.flush()
    audit.write_event(
        db,
        event_type="reviewee.results_acknowledged",
        summary=f"Reviewee {reviewee.email_or_identifier} acknowledged results",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.snapshot(
            {
                "reviewee_id": reviewee.id,
                "acknowledged_at": now.isoformat(),
            }
        ),
        correlation_id=correlation_id,
    )
    db.commit()
    return True


__all__ = [
    "RevieweeOperationError",
    "acknowledge_results",
    "create_reviewee",
    "update_reviewee",
    "bulk_inactivate",
    "bulk_reactivate",
]
