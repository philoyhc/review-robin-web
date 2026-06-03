"""Coverage / staleness / counts + roster queries.

Read-only (with one destructive tail — ``delete_all_assignments``)
summaries the Validate page, the Workflow card, and the Assignments
page consume. Writes nothing apart from the explicit
``delete_all_assignments`` destructive op.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Assignment,
    Instrument,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import audit, session_lifecycle as lifecycle
from app.services._queries import session_scoped, slot_has_data


PAIR_PREVIEW_LIMIT = 200


def reviewer_fields_with_data(db: Session, session_id: int) -> list[str]:
    """CSV column names of reviewer fields that hold at least one value."""
    labels: list[str] = []
    has_any = (
        db.execute(
            session_scoped(Reviewer.id, session_id).limit(1)
        ).first()
        is not None
    )
    if has_any:
        labels.extend(["ReviewerName", "ReviewerEmail"])
    for slot in (1, 2, 3):
        if slot_has_data(
            db, session_id=session_id, column=getattr(Reviewer, f"tag_{slot}")
        ):
            labels.append(f"ReviewerTag{slot}")
    return labels


def reviewee_fields_with_data(db: Session, session_id: int) -> list[str]:
    """CSV column names of reviewee fields that hold at least one value."""
    labels: list[str] = []
    has_any = (
        db.execute(
            session_scoped(Reviewee.id, session_id).limit(1)
        ).first()
        is not None
    )
    if has_any:
        labels.extend(["RevieweeName", "RevieweeEmail"])
    if slot_has_data(
        db, session_id=session_id, column=Reviewee.profile_link
    ):
        labels.append("PhotoLink")
    for slot in (1, 2, 3):
        if slot_has_data(
            db, session_id=session_id, column=getattr(Reviewee, f"tag_{slot}")
        ):
            labels.append(f"RevieweeTag{slot}")
    return labels


def assignment_fields_with_data(db: Session, session_id: int) -> list[str]:
    """CSV column names of assignment fields that hold at least one value.

    Pair-context columns (``PairContextN``) reflect the post-15D
    state — values come from the ``relationships`` table now,
    not the retired ``Assignment.context`` JSON column. The
    ``AssignmentContextN`` family retired entirely in 15D PR 6b
    (operator-typed via the manual CSV only; manual CSV no longer
    writes context after the column drop).
    """

    labels: list[str] = []
    has_any = (
        db.execute(
            session_scoped(Assignment.id, session_id).limit(1)
        ).first()
        is not None
    )
    if not has_any:
        return labels
    labels.extend(["ReviewerEmail", "RevieweeEmail", "IncludeAssignment"])
    for slot in (1, 2, 3):
        if slot_has_data(
            db,
            session_id=session_id,
            column=getattr(Relationship, f"tag_{slot}"),
        ):
            labels.append(f"PairContext{slot}")
    return labels


def display_source_presence(db: Session, session_id: int) -> dict[str, bool]:
    """Composed view: which display-source CSV column names are populated.

    Reuses the three per-table helpers so we don't run a parallel set of
    queries dedicated to the instruments page.
    """
    fields = (
        set(reviewer_fields_with_data(db, session_id))
        | set(reviewee_fields_with_data(db, session_id))
        | set(assignment_fields_with_data(db, session_id))
    )
    return {key: True for key in fields}


def get_or_create_default_instrument(
    db: Session, review_session: ReviewSession
) -> Instrument:
    """Return the session's default instrument, creating it if missing.

    Thin alias for ``app.services.instruments.ensure_default_instrument``;
    kept here as the seam ``replace_assignments`` uses to pick the target
    instrument for newly generated rows.
    """
    from app.services.instruments import ensure_default_instrument

    return ensure_default_instrument(db, review_session)


def existing_count(
    db: Session,
    session_id: int,
    *,
    instrument_id: int | None = None,
) -> int:
    """Count ``Assignment`` rows for the session, optionally scoped to
    a single instrument.
    """
    stmt = session_scoped(Assignment.id, session_id)
    if instrument_id is not None:
        stmt = stmt.where(Assignment.instrument_id == instrument_id)
    return len(db.execute(stmt).all())


def included_count_per_instrument(
    db: Session, session_id: int
) -> dict[int, int]:
    """Materialised ``Assignment`` row count keyed by
    ``instrument_id``, restricted to rows where ``include=True``.

    Drives the per-instrument **Included** count on the Assignments
    page status table — the counterpart of
    :func:`existing_count_per_instrument`, which surfaces the total
    row count regardless of ``include``.
    """
    rows = db.execute(
        session_scoped(
            Assignment.instrument_id, session_id
        ).add_columns(func.count(Assignment.id))
        .where(Assignment.include.is_(True))
        .group_by(Assignment.instrument_id)
    ).all()
    return {instrument_id: count for instrument_id, count in rows}


def existing_count_per_instrument(
    db: Session, session_id: int
) -> dict[int, int]:
    """Materialised ``Assignment`` row count keyed by ``instrument_id``.

    Drives the per-instrument **Generated** count on the Slice 3a
    Assignments page status blocks. Instruments with zero rows
    (never generated, or wiped after a roster edit) are absent from
    the dict — callers default-to-zero on lookup.
    """
    rows = db.execute(
        session_scoped(
            Assignment.instrument_id, session_id
        ).add_columns(func.count(Assignment.id))
        .group_by(Assignment.instrument_id)
    ).all()
    return {instrument_id: count for instrument_id, count in rows}


def compute_staleness(
    rule_id: int | None,
    eligible_count: int,
    generated_count: int,
) -> bool:
    """Return ``True`` when the instrument is pinned but its
    materialised pair count diverges from what the engine would
    produce now. ``False`` when no rule is pinned or counts match.

    Catches: never-generated pinned instruments
    (``eligible > 0``, ``generated == 0``), instruments whose
    pinned rule changed post-Generate, instruments whose roster /
    relationships changed post-Generate. The view-shape
    ``InstrumentStatusBlock.is_stale`` field, the per-page
    ``any_stale`` aggregate, and the ``instruments.stale_generated``
    validation rule all share this one definition.
    """
    return rule_id is not None and eligible_count != generated_count


def latest_generated_event_per_instrument(
    db: Session, session_id: int
) -> dict[int, Any]:
    """Latest ``assignments.generated`` ``AuditEvent`` keyed by
    ``refs.instrument_id`` for the given session.

    Reads only events with an integer ``refs.instrument_id`` slot —
    pre-Slice-1 aggregated events (no instrument scope) are skipped.
    Drives the "last generated …" timestamp on the per-instrument
    status blocks introduced in Slice 3a.
    """
    from app.db.models import AuditEvent

    events = db.execute(
        select(AuditEvent)
        .where(
            AuditEvent.session_id == session_id,
            AuditEvent.event_type == "assignments.generated",
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    ).scalars()
    latest: dict[int, AuditEvent] = {}
    for event in events:
        detail = event.detail or {}
        refs = detail.get("refs") or {}
        instrument_id = refs.get("instrument_id")
        if not isinstance(instrument_id, int):
            continue
        # First seen wins — events are pre-sorted desc by created_at.
        latest.setdefault(instrument_id, event)
    return latest


def list_reviewers(db: Session, session_id: int) -> list[Reviewer]:
    return list(
        db.execute(
            session_scoped(Reviewer, session_id).order_by(Reviewer.id)
        ).scalars()
    )


def list_reviewees(db: Session, session_id: int) -> list[Reviewee]:
    return list(
        db.execute(
            session_scoped(Reviewee, session_id).order_by(Reviewee.id)
        ).scalars()
    )


def _apply_pair_search(stmt, search: str, search_by: str = "all"):
    """Add the reviewer / reviewee free-text filter to a pairs query
    — case-insensitive substring match on name or email (Segment
    13C Assignments-page search). ``search_by`` scopes which side
    is matched: ``reviewer`` / ``reviewee`` match only that side;
    anything else (``all``) matches either."""
    term = f"%{search.strip()}%"
    stmt = stmt.join(
        Reviewer, Assignment.reviewer_id == Reviewer.id
    ).join(Reviewee, Assignment.reviewee_id == Reviewee.id)
    reviewer_match = or_(
        Reviewer.name.ilike(term), Reviewer.email.ilike(term)
    )
    reviewee_match = or_(
        Reviewee.name.ilike(term),
        Reviewee.email_or_identifier.ilike(term),
    )
    if search_by == "reviewer":
        return stmt.where(reviewer_match)
    if search_by == "reviewee":
        return stmt.where(reviewee_match)
    return stmt.where(or_(reviewer_match, reviewee_match))


def list_pairs(
    db: Session,
    session_id: int,
    *,
    limit: int = PAIR_PREVIEW_LIMIT,
    search: str | None = None,
    search_by: str = "all",
) -> list[Assignment]:
    """Return saved Assignment rows with reviewer + reviewee + instrument
    eagerly loaded.

    Ordered by (reviewer_id, reviewee_id, instrument_id) to match the
    FullMatrix preview shape and keep instrument rows next to each
    other within the same pair on the diagnostic Assignment-pairs
    table. ``search`` (when set) filters to rows whose reviewer
    and/or reviewee name / email matches the term, scoped by
    ``search_by`` (``all`` / ``reviewer`` / ``reviewee``).
    """
    stmt = session_scoped(Assignment, session_id).options(
        joinedload(Assignment.reviewer),
        joinedload(Assignment.reviewee),
        joinedload(Assignment.instrument),
    )
    if search and search.strip():
        stmt = _apply_pair_search(stmt, search, search_by)
    stmt = stmt.order_by(
        Assignment.reviewer_id,
        Assignment.reviewee_id,
        Assignment.instrument_id,
    ).limit(limit)
    return list(db.execute(stmt).scalars())


def count_pairs(
    db: Session,
    session_id: int,
    *,
    search: str | None = None,
    search_by: str = "all",
) -> int:
    """Count saved Assignment rows for the session, optionally
    filtered by the reviewer / reviewee free-text ``search``
    (scoped by ``search_by``)."""
    stmt = session_scoped(Assignment.id, session_id)
    if search and search.strip():
        stmt = _apply_pair_search(stmt, search, search_by)
    return len(db.execute(stmt).all())


def delete_all_assignments(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str,
    instrument_id: int | None = None,
) -> int:
    """Remove ``Assignment`` rows from the session.

    ``instrument_id=None`` (default): clears every row and resets
    ``assignment_mode`` to NULL. ``instrument_id=<id>``: scoped delete
    that leaves rows on other instruments untouched and does NOT
    clear ``assignment_mode``.
    """
    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason="assignments_deleted_all",
        correlation_id=correlation_id,
    )
    stmt = session_scoped(Assignment, review_session.id)
    if instrument_id is not None:
        stmt = stmt.where(Assignment.instrument_id == instrument_id)
    rows = list(db.execute(stmt).scalars())
    deleted = len(rows)
    for row in rows:
        db.delete(row)
    if instrument_id is None:
        review_session.assignment_mode = None
    db.flush()

    refs: dict[str, int] | None = (
        {"instrument_id": instrument_id} if instrument_id is not None else None
    )
    audit.write_event(
        db,
        event_type="assignments.deleted_all",
        summary=f"Deleted all {deleted} assignments",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(deleted=deleted),
        refs=refs,
        correlation_id=correlation_id,
    )
    db.commit()
    return deleted
