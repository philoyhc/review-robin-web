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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
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


# Which ``Assignment`` column points back at each roster model, for the
# exact cascade count below. Observers and Relationships are absent on
# purpose: nothing references them, so deleting one destroys no
# assignment and no response — measured from the model graph
# (Segment 19I Item 2 PR 2), which is what answers the item's open
# question about whether Relationships needs a response-loss gate. It
# does not.
_ASSIGNMENT_FK = {
    Reviewer: Assignment.reviewer_id,
    Reviewee: Assignment.reviewee_id,
}


def cascade_counts(
    db: Session, *, model: type, ids: list[int]
) -> tuple[int, int]:
    """``(assignments, responses)`` that deleting ``ids`` would take
    with them, for *these* rows rather than the whole session.

    ``delete_all`` can only say how many assignments exist; a selected
    delete knows which rows are going and can count exactly what they
    carry, which is what lets the confirmation name a real number.
    Returns ``(0, 0)`` for models nothing references.
    """
    column = _ASSIGNMENT_FK.get(model)
    if column is None or not ids:
        return 0, 0
    assignment_ids = list(
        db.execute(select(Assignment.id).where(column.in_(ids))).scalars()
    )
    if not assignment_ids:
        return 0, 0
    responses = db.execute(
        select(func.count())
        .select_from(Response)
        .where(Response.assignment_id.in_(assignment_ids))
    ).scalar_one()
    return len(assignment_ids), int(responses)


def bulk_delete(
    db: Session,
    *,
    review_session: ReviewSession,
    model: type,
    ids: list[int],
    error_cls: type[Exception],
    event_type: str,
    entity_noun: str,
    user: User,
    correlation_id: str | None,
) -> tuple[int, int, int]:
    """Delete every ``model`` row in ``ids``, scoped to
    ``review_session``. Returns ``(deleted, assignments, responses)``.

    Sibling of :func:`bulk_set_status`, and deliberately the same
    shape: session-scoped, one audit event, one commit. It raises
    ``error_cls("not_in_session", ...)`` on an id from another session
    for the same reason that one does — and more so, since a silently
    skipped id here means a row the operator asked to delete is still
    there and nothing said so.

    The ORM cascades do the rest of the work:
    ``Reviewer``/``Reviewee`` → ``assignments`` → ``responses``, all
    ``delete-orphan``, plus a reviewer's ``invitations``. That is
    inherited rather than reimplemented, exactly as ``_delete_all``
    inherits it.
    """
    if not ids:
        return 0, 0, 0

    rows = list(
        db.execute(
            select(model)
            .where(model.session_id == review_session.id, model.id.in_(ids))
            .order_by(model.id)
        ).scalars()
    )
    missing = set(ids) - {row.id for row in rows}
    if missing:
        raise error_cls(
            "not_in_session",
            f"{entity_noun.capitalize()} ids {sorted(missing)} do not "
            f"belong to session {review_session.id}.",
        )

    row_ids = [row.id for row in rows]
    assignments, responses = cascade_counts(db, model=model, ids=row_ids)

    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason=f"{entity_noun}_bulk_deleted",
        correlation_id=correlation_id,
    )

    deleted = len(rows)
    for row in rows:
        db.delete(row)
    db.flush()

    audit.write_event(
        db,
        event_type=event_type,
        summary=(
            f"Deleted {deleted} selected {entity_noun}"
            f"{'' if deleted == 1 else 's'}"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(
            deleted=deleted,
            cascaded_assignments=assignments,
            cascaded_responses=responses,
        ),
        correlation_id=correlation_id,
    )
    db.commit()
    return deleted, assignments, responses
