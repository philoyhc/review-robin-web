"""Shared bulk status-flip for the roster services.

The reviewer / reviewee / observer / relationship services each grew a
byte-for-byte copy of the same "flip status on a session-scoped set of
ids, skip rows already at the target, emit one snapshot audit event"
algorithm (audit S5). This is the single implementation; each caller
supplies only what genuinely differs — the model, its status
normaliser, its ``*OperationError`` class, and its entity noun.

See ``guide/segment_19B_consistency.md`` (S5).
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import audit
from app.services import session_lifecycle as lifecycle


def bulk_set_status(
    db: Session,
    *,
    review_session: ReviewSession,
    model: type,
    ids: list[int],
    target_status: str,
    normalise_status: Callable[[str], str],
    error_cls: type[Exception],
    event_type: str,
    entity_noun: str,
    user: User,
    correlation_id: str | None,
) -> list[int]:
    """Flip ``status`` to ``target_status`` on every ``model`` row in
    ``ids`` that isn't already there, scoped to ``review_session``.

    Returns the ids actually flipped (empty when ``ids`` is empty or
    every row already sits at the target). Raises
    ``error_cls("not_in_session", ...)`` if any id doesn't belong to
    the session. Emits a single ``event_type`` snapshot audit event
    keyed ``{f"{entity_noun}_ids": flipped}``.
    """
    clean_target = normalise_status(target_status)
    if not ids:
        return []

    candidates = list(
        db.execute(
            select(model)
            .where(model.session_id == review_session.id, model.id.in_(ids))
            .order_by(model.id)
        ).scalars()
    )
    missing = set(ids) - {row.id for row in candidates}
    if missing:
        raise error_cls(
            "not_in_session",
            f"{entity_noun.capitalize()} ids {sorted(missing)} do not "
            f"belong to session {review_session.id}.",
        )

    flipped = [row for row in candidates if row.status != clean_target]
    if not flipped:
        return []

    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason=f"{entity_noun}_bulk_status_change",
        correlation_id=correlation_id,
    )

    flipped_ids = [row.id for row in flipped]
    for row in flipped:
        row.status = clean_target
    db.flush()

    audit.write_event(
        db,
        event_type=event_type,
        summary=(
            f"Flipped {len(flipped_ids)} {entity_noun}"
            f"{'' if len(flipped_ids) == 1 else 's'} → {clean_target}"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.snapshot({f"{entity_noun}_ids": flipped_ids}),
        correlation_id=correlation_id,
    )
    db.commit()
    return flipped_ids
