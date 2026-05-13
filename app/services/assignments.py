from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Assignment,
    Instrument,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.schemas.assignments import AssignmentMode
from app.services import audit, session_lifecycle as lifecycle
from app.services._queries import session_scoped

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
        col = getattr(Reviewer, f"tag_{slot}")
        found = db.execute(
            session_scoped(Reviewer.id, session_id)
            .where(col.is_not(None))
            .where(col != "")
            .limit(1)
        ).first()
        if found is not None:
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
    profile_found = db.execute(
        session_scoped(Reviewee.id, session_id)
        .where(Reviewee.profile_link.is_not(None))
        .where(Reviewee.profile_link != "")
        .limit(1)
    ).first()
    if profile_found is not None:
        labels.append("PhotoLink")
    for slot in (1, 2, 3):
        col = getattr(Reviewee, f"tag_{slot}")
        found = db.execute(
            session_scoped(Reviewee.id, session_id)
            .where(col.is_not(None))
            .where(col != "")
            .limit(1)
        ).first()
        if found is not None:
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
        col = getattr(Relationship, f"tag_{slot}")
        found = db.execute(
            select(Relationship.id)
            .where(Relationship.session_id == session_id)
            .where(col.is_not(None))
            .where(col != "")
            .limit(1)
        ).first()
        if found is not None:
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


def _is_active(row: Reviewer | Reviewee) -> bool:
    return (row.status or "active") == "active"


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


def existing_count_per_instrument(
    db: Session, session_id: int
) -> dict[int, int]:
    """Materialised ``Assignment`` row count keyed by ``instrument_id``.

    Drives the per-instrument **Generated** count on the Slice 3a
    Assignments page status blocks. Instruments with zero rows
    (never generated, or wiped after a roster edit) are absent from
    the dict — callers default-to-zero on lookup.
    """
    from sqlalchemy import func

    rows = db.execute(
        session_scoped(
            Assignment.instrument_id, session_id
        ).add_columns(func.count(Assignment.id))
        .group_by(Assignment.instrument_id)
    ).all()
    return {instrument_id: count for instrument_id, count in rows}


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


def is_self_review(reviewer: Reviewer, reviewee: Reviewee) -> bool:
    identifier = reviewee.email_or_identifier
    if "@" not in identifier:
        return False
    return reviewer.email.casefold() == identifier.casefold()


def count_self_review_candidates(
    reviewers: Iterable[Reviewer],
    reviewees: Iterable[Reviewee],
) -> int:
    """Total self-review pairs across the full reviewer x reviewee matrix.

    Independent of whether the operator chose to exclude self-reviews —
    this is the population from which exclusion is drawn.
    """
    reviewers_list = list(reviewers)
    reviewees_list = list(reviewees)
    return sum(
        1
        for r in reviewers_list
        for ree in reviewees_list
        if is_self_review(r, ree)
    )


def count_self_reviews_in_assignments(
    db: Session, session_id: int
) -> int:
    """Count saved Assignment rows where reviewer.email matches reviewee identifier."""
    rows = db.execute(
        select(Assignment, Reviewer, Reviewee)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        .where(Assignment.session_id == session_id)
    ).all()
    return sum(1 for _, reviewer, reviewee in rows if is_self_review(reviewer, reviewee))


def self_review_breakdown_per_instrument(
    db: Session, session_id: int
) -> dict[int, tuple[int, int]]:
    """Per-instrument ``(active, deactivated)`` counts for
    self-review rows. Drives the per-instrument **Self review**
    column on the Assignments-page status blocks: the pill text is
    ``active + deactivated``; the checkbox state is derived from
    the (active, deactivated) ratio (all-active → checked;
    all-deactivated → unchecked; mixed → ``indeterminate``).

    Instruments with no self-review rows are absent from the dict.
    Replaces the session-wide ``self_review_include_breakdown`` —
    the per-instrument variant subsumes it for the only consumer
    that's still around (the Assignments page).
    """
    rows = db.execute(
        select(Assignment, Reviewer, Reviewee)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        .where(Assignment.session_id == session_id)
    ).all()
    out: dict[int, tuple[int, int]] = {}
    for assignment, reviewer, reviewee in rows:
        if not is_self_review(reviewer, reviewee):
            continue
        active, deactivated = out.get(assignment.instrument_id, (0, 0))
        if assignment.include:
            active += 1
        else:
            deactivated += 1
        out[assignment.instrument_id] = (active, deactivated)
    return out


def set_instrument_self_reviews_active(
    db: Session,
    *,
    review_session: ReviewSession,
    instrument_id: int,
    user: User,
    active: bool,
    correlation_id: str,
) -> int:
    """Bulk-flip self-review rows' ``include`` flag scoped to one
    instrument. Mirror of the retired session-wide
    ``set_self_reviews_active`` — the per-instrument Self review
    column on the Slice 3a Assignments-page status blocks owns
    this surface now.

    Returns the row count actually flipped (rows whose previous
    ``include`` differed from ``active``). Mixed states converge:
    a partially-active instrument flipped to ``active=False``
    moves every still-active row to ``False``; a partially-active
    one flipped to ``active=True`` moves every deactivated row to
    ``True``. Audit event
    ``assignments.instrument_self_reviews_active_set`` carries
    ``counts.flipped`` + ``context.active`` +
    ``refs.instrument_id``.
    """
    rows = db.execute(
        select(Assignment, Reviewer, Reviewee)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        .where(
            Assignment.session_id == review_session.id,
            Assignment.instrument_id == instrument_id,
        )
    ).all()
    flipped = 0
    for assignment, reviewer, reviewee in rows:
        if not is_self_review(reviewer, reviewee):
            continue
        if assignment.include != active:
            assignment.include = active
            flipped += 1
    db.flush()
    audit.write_event(
        db,
        event_type="assignments.instrument_self_reviews_active_set",
        summary=(
            f"Self-reviews on instrument {instrument_id} bulk-set "
            f"to {'active' if active else 'inactive'} "
            f"({flipped} row{'s' if flipped != 1 else ''} flipped)"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(flipped=flipped),
        context={"active": active},
        refs={"instrument_id": instrument_id},
        correlation_id=correlation_id,
    )
    db.commit()
    return flipped


def generate_full_matrix(
    reviewers: Iterable[Reviewer],
    reviewees: Iterable[Reviewee],
    *,
    exclude_self_review: bool,
) -> tuple[list[tuple[Reviewer, Reviewee]], dict[str, int]]:
    """Return (pairs, excluded_counts). Deterministic ordering by id.

    ``excluded_counts`` is a generic map keyed by reason; today's keys are
    ``self_review``, ``inactive_reviewer``, ``inactive_reviewee``. The
    audit detail uses the same shape so future RuleBased exclusions can
    plug in additional reasons without a schema change.
    """
    reviewers_list = list(reviewers)
    reviewees_list = list(reviewees)
    inactive_reviewers = sum(1 for r in reviewers_list if not _is_active(r))
    inactive_reviewees = sum(1 for r in reviewees_list if not _is_active(r))

    active_reviewers = sorted(
        (r for r in reviewers_list if _is_active(r)), key=lambda r: r.id
    )
    active_reviewees = sorted(
        (r for r in reviewees_list if _is_active(r)), key=lambda r: r.id
    )
    pairs: list[tuple[Reviewer, Reviewee]] = []
    excluded_self = 0
    for reviewer in active_reviewers:
        for reviewee in active_reviewees:
            if exclude_self_review and is_self_review(reviewer, reviewee):
                excluded_self += 1
                continue
            pairs.append((reviewer, reviewee))

    excluded: dict[str, int] = {}
    if excluded_self:
        excluded["self_review"] = excluded_self
    if inactive_reviewers:
        excluded["inactive_reviewer"] = inactive_reviewers
    if inactive_reviewees:
        excluded["inactive_reviewee"] = inactive_reviewees
    return pairs, excluded


def coverage_stats(
    reviewers: list[Reviewer],
    reviewees: list[Reviewee],
    pairs: list[tuple[Reviewer, Reviewee]],
) -> dict[str, Any]:
    reviewer_ids_with_pair = {r.id for r, _ in pairs}
    reviewee_ids_with_pair = {e.id for _, e in pairs}
    return {
        "total": len(pairs),
        "reviewers_total": len(reviewers),
        "reviewees_total": len(reviewees),
        "reviewers_covered": len(reviewer_ids_with_pair),
        "reviewees_covered": len(reviewee_ids_with_pair),
        "reviewers_uncovered": [
            r for r in reviewers if r.id not in reviewer_ids_with_pair
        ],
        "reviewees_uncovered": [
            r for r in reviewees if r.id not in reviewee_ids_with_pair
        ],
    }


def _session_rule_set_to_schema(row: SessionRuleSet) -> Any:
    """Build a ``RuleSetSchema`` from a ``SessionRuleSet`` row.

    The engine accepts any ``RuleSetSchema`` regardless of origin tier;
    this adapter is the session-tier mirror of the operator-tier
    rehydrate dance at ``_rule_builder.py::rule_based_generate``.
    """
    from pydantic import TypeAdapter

    from app.schemas.rules import (
        Combinator,
        Rule,
        RuleSetOptions,
        RuleSetSchema,
        RuleSetScope,
    )

    rule_adapter = TypeAdapter(Rule)
    return RuleSetSchema(
        id=row.id,
        name=row.name,
        description=row.description or "",
        scope=RuleSetScope.personal,
        combinator=Combinator(row.combinator),
        rules=[rule_adapter.validate_python(payload) for payload in row.rules_json],
        options=RuleSetOptions(
            excludeSelfReviews=row.exclude_self_reviews,
            seed=row.seed,
        ),
    )


def _materialise_one_instrument(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    instrument: Instrument,
    session_rule_set: SessionRuleSet,
    reviewers: list[Reviewer],
    reviewees: list[Reviewee],
    pair_context_lookup: dict[tuple[int, int], Relationship],
    mode: AssignmentMode,
    override_exclude_self_reviews: bool | None,
    correlation_id: str,
) -> tuple[int, int]:
    """Materialise ``Assignment`` rows for a single instrument.

    Runs the engine against the instrument's pinned ``SessionRuleSet``,
    deletes existing rows scoped to this instrument only, inserts the
    new pair fan-out, and emits one ``assignments.generated`` audit
    event keyed by ``refs.instrument_id``.

    Returns ``(replaced, new)`` for this instrument.
    """
    from app.services.rules import engine

    rule_set_schema = _session_rule_set_to_schema(session_rule_set)
    result = engine.evaluate(
        rule_set_schema,
        reviewers=reviewers,
        reviewees=reviewees,
        override_exclude_self_reviews=override_exclude_self_reviews,
        revision_seed=session_rule_set.id,
        pair_context_lookup=pair_context_lookup,
    )

    replaced_here = existing_count(
        db, review_session.id, instrument_id=instrument.id
    )
    db.execute(
        delete(Assignment)
        .where(Assignment.session_id == review_session.id)
        .where(Assignment.instrument_id == instrument.id)
    )

    new_here = 0
    for reviewer, reviewee in result.pairs:
        if is_self_review(reviewer, reviewee):
            pair_include = review_session.self_reviews_active
        else:
            pair_include = True
        db.add(
            Assignment(
                session_id=review_session.id,
                reviewer_id=reviewer.id,
                reviewee_id=reviewee.id,
                instrument_id=instrument.id,
                include=pair_include,
                created_by_mode=mode.value,
            )
        )
        new_here += 1
    db.flush()

    counts_kwargs: dict[str, int] = {
        "new": new_here,
        "replaced": replaced_here,
        "pairs": len(result.pairs),
        "instruments": 1,
    }
    for reason, n in result.excluded_counts.items():
        counts_kwargs[f"excluded_{reason}"] = n
    context: dict[str, str | int | bool] = {"mode": mode.value}
    if override_exclude_self_reviews is not None:
        context["exclude_self_reviews"] = override_exclude_self_reviews
    refs: dict[str, int] = {
        "instrument_id": instrument.id,
        "rule_set_id": session_rule_set.id,
    }
    audit.write_event(
        db,
        event_type="assignments.generated",
        summary=(
            f"Generated {new_here} assignments for {instrument.name!r} "
            f"({len(result.pairs)} pair{'' if len(result.pairs) == 1 else 's'}) "
            f"via {mode.value} (replaced {replaced_here})"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(**counts_kwargs),
        context=context,
        refs=refs,
        correlation_id=correlation_id,
    )
    return replaced_here, new_here


def replace_assignments(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str,
    instrument_id: int | None = None,
    mode: AssignmentMode = AssignmentMode.rule_based,
    override_exclude_self_reviews: bool | None = None,
) -> tuple[int, int]:
    """Materialise per-instrument ``Assignment`` rows from each
    instrument's pinned ``rule_set_id``.

    ``instrument_id=None`` (default): iterate every instrument in the
    session whose ``rule_set_id`` is non-NULL, run the rule engine
    per-instrument against that instrument's pinned
    ``session_rule_sets`` row, and write per-instrument pair fan-outs.
    Instruments with NULL ``rule_set_id`` are skipped silently — they
    are "no rule pinned yet", not an error condition.

    ``instrument_id=<id>``: scope to that single instrument only. The
    instrument's ``rule_set_id`` must be non-NULL; raises ``ValueError``
    otherwise.

    Returns aggregate ``(replaced, new)`` ``Assignment`` row counts
    across every instrument processed. Emits one
    ``assignments.generated`` audit event per processed instrument
    with ``refs.instrument_id`` set.

    When zero instruments are processed (no pinned rules in scope),
    returns ``(0, 0)`` and does not invalidate the validated
    lifecycle state.
    """
    get_or_create_default_instrument(db, review_session)
    instruments_query = (
        session_scoped(Instrument, review_session.id)
        .order_by(Instrument.order, Instrument.id)
    )
    if instrument_id is not None:
        instruments_query = instruments_query.where(Instrument.id == instrument_id)
    all_instruments = list(db.execute(instruments_query).scalars())

    if instrument_id is not None and not all_instruments:
        raise ValueError(
            f"instrument {instrument_id} not found in session "
            f"{review_session.id}"
        )

    if instrument_id is not None:
        # Single-instrument scope: the caller named the target; we
        # require its ``rule_set_id`` to be pinned.
        if all_instruments[0].rule_set_id is None:
            raise ValueError(
                f"instrument {instrument_id} has no rule pinned "
                "(rule_set_id is NULL)"
            )
        targets = list(all_instruments)
    else:
        # Cross-instrument scope: silently skip unpinned ones.
        targets = [i for i in all_instruments if i.rule_set_id is not None]

    if not targets:
        return 0, 0

    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason="assignments_generated",
        correlation_id=correlation_id,
    )

    reviewers = list_reviewers(db, review_session.id)
    reviewees = list_reviewees(db, review_session.id)
    from app.services import relationships as relationships_service

    pair_context_lookup = relationships_service.pair_context_lookup(
        db, review_session.id
    )

    rule_set_ids = {i.rule_set_id for i in targets}
    rule_set_rows = {
        row.id: row
        for row in db.execute(
            select(SessionRuleSet).where(SessionRuleSet.id.in_(rule_set_ids))
        ).scalars()
    }

    total_replaced = 0
    total_new = 0
    for instrument in targets:
        session_rule_set = rule_set_rows.get(instrument.rule_set_id)
        if session_rule_set is None:
            # Dangling FK shouldn't happen given the SET NULL cascade;
            # treat as a data-integrity bug.
            raise ValueError(
                f"instrument {instrument.id} points at missing "
                f"session_rule_set {instrument.rule_set_id}"
            )
        replaced_here, new_here = _materialise_one_instrument(
            db,
            review_session=review_session,
            user=user,
            instrument=instrument,
            session_rule_set=session_rule_set,
            reviewers=reviewers,
            reviewees=reviewees,
            pair_context_lookup=pair_context_lookup,
            mode=mode,
            override_exclude_self_reviews=override_exclude_self_reviews,
            correlation_id=correlation_id,
        )
        total_replaced += replaced_here
        total_new += new_here

    review_session.assignment_mode = mode.value
    db.flush()
    db.commit()

    # Lazy-seed pair_context display fields for any populated slots
    # — see guide/unfinished_business item #14.
    from app.services.instruments import seed_display_fields_from_assignments

    if seed_display_fields_from_assignments(db, review_session):
        db.commit()
    return total_replaced, total_new


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


def list_pairs(
    db: Session, session_id: int, *, limit: int = PAIR_PREVIEW_LIMIT
) -> list[Assignment]:
    """Return saved Assignment rows with reviewer + reviewee + instrument
    eagerly loaded.

    Ordered by (reviewer_id, reviewee_id, instrument_id) to match the
    FullMatrix preview shape and keep instrument rows next to each
    other within the same pair on the diagnostic Assignment-pairs
    table.
    """
    stmt = (
        session_scoped(Assignment, session_id)
        .options(
            joinedload(Assignment.reviewer),
            joinedload(Assignment.reviewee),
            joinedload(Assignment.instrument),
        )
        .order_by(
            Assignment.reviewer_id,
            Assignment.reviewee_id,
            Assignment.instrument_id,
        )
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


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
