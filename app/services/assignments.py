from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Assignment,
    Instrument,
    Relationship,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.schemas.assignments import AssignmentMode
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
    from sqlalchemy import func

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


def classify_self_review(
    db: Session,
    *,
    session_id: int,
    rows: list[tuple[Assignment, Reviewer, Reviewee]],
) -> dict[int, bool]:
    """The canonical self-review classification for a set of
    ``(Assignment, Reviewer, Reviewee)`` rows on one session.

    Returns ``{assignment_id: is_self_review}`` for every row passed
    in. The rule is documented in ``spec/assignments.md`` § *Self-
    review policy*:

    * **Individual-scoped instrument** (``instrument.group_kind`` is
      ``None``): per-row pair match — true iff
      :func:`is_self_review` returns ``True`` on this row's
      reviewer / reviewee.
    * **Group-scoped instrument**: the whole-group rule — true iff
      the reviewer is themselves a member of the group they're
      reviewing (i.e. any ``(R, member)`` pair in that group has
      ``member == R`` by the pair-level test). When the rule fires,
      *every* assignment in the group is flagged, not just the
      ``(R, R)`` cell.

    Single canonical computation surface — every write site
    (Assignment creation / fan-out / recompute) and the PR-1 backfill
    route through this function so the rule lives in exactly one
    place. See ``guide/self_review_consolidate.md``.
    """
    from app.services.responses import group_keys

    group_key_by_assignment = group_keys(
        db,
        assignments=[assignment for assignment, _, _ in rows],
        session_id=session_id,
    )
    # (group instrument, reviewer) -> group key of the group that
    # reviewer is a member of (i.e. groups where the (R, R) member
    # pair exists, identifying the group as a self-review group).
    self_group_key: dict[tuple[int, int], tuple[str, ...]] = {}
    for assignment, reviewer, reviewee in rows:
        if assignment.id in group_key_by_assignment and is_self_review(
            reviewer, reviewee
        ):
            self_group_key[
                (assignment.instrument_id, assignment.reviewer_id)
            ] = group_key_by_assignment[assignment.id]
    result: dict[int, bool] = {}
    for assignment, reviewer, reviewee in rows:
        group_key = group_key_by_assignment.get(assignment.id)
        if group_key is None:
            # Individual-scoped instrument.
            result[assignment.id] = is_self_review(reviewer, reviewee)
        else:
            # Group-scoped: whole-group rule.
            result[assignment.id] = (
                self_group_key.get(
                    (assignment.instrument_id, assignment.reviewer_id)
                )
                == group_key
            )
    return result


def _self_review_assignment_ids(
    db: Session,
    *,
    session_id: int,
    rows: list[tuple[Assignment, Reviewer, Reviewee]],
) -> set[int]:
    """Thin wrapper over :func:`classify_self_review` that returns
    the set of assignment ids that count as self-reviews. Kept for
    callsites that already work in the set-of-ids shape."""
    return {
        assignment_id
        for assignment_id, is_self in classify_self_review(
            db, session_id=session_id, rows=rows
        ).items()
        if is_self
    }


def recompute_self_review_classification(
    db: Session, *, session_id: int
) -> int:
    """Recompute :attr:`Assignment.is_self_review` for every
    assignment in the session and persist any row whose stored
    value diverged from what :func:`classify_self_review` now
    returns.

    The whole-group rule requires seeing every ``(R, member)``
    pair in a group to detect self-groups correctly; the
    whole-session scope is the only one that always includes
    them all without expensive expansion. Beta-scale session
    sizes make this cheap; if it ever turns hot a scoped
    variant can wrap the same canonical helper.

    Every write site that creates / changes assignments, and
    every edit site that can shift the rule's input
    (reviewer email, reviewee identifier or boundary tag,
    relationship boundary tag, instrument ``group_kind``)
    calls this after its own flush. The function flushes
    automatically when at least one row changed.

    Returns the number of rows whose stored value changed.
    """
    rows = db.execute(
        select(Assignment, Reviewer, Reviewee)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        .where(Assignment.session_id == session_id)
    ).all()
    if not rows:
        return 0
    classification = classify_self_review(
        db, session_id=session_id, rows=rows
    )
    changed = 0
    for assignment, _, _ in rows:
        new_value = classification[assignment.id]
        if assignment.is_self_review != new_value:
            assignment.is_self_review = new_value
            changed += 1
    if changed:
        db.flush()
    return changed


def self_review_breakdown_per_instrument(
    db: Session, session_id: int
) -> dict[int, tuple[int, int]]:
    """Per-instrument ``(active, deactivated)`` counts for
    self-review assignments. Drives the per-instrument **Self
    review** column on the Assignments-page status blocks: the
    pill text is ``active + deactivated``; the checkbox state is
    derived from the (active, deactivated) ratio (all-active →
    checked; all-deactivated → unchecked; mixed →
    ``indeterminate``).

    "Self-review assignment" is group-aware — see
    :func:`_self_review_assignment_ids`. Instruments with none are
    absent from the dict.
    """
    rows = db.execute(
        select(Assignment, Reviewer, Reviewee)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        .where(Assignment.session_id == session_id)
    ).all()
    self_ids = _self_review_assignment_ids(
        db, session_id=session_id, rows=rows
    )
    out: dict[int, tuple[int, int]] = {}
    for assignment, _reviewer, _reviewee in rows:
        if assignment.id not in self_ids:
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
    self_ids = _self_review_assignment_ids(
        db, session_id=review_session.id, rows=rows
    )
    flipped = 0
    for assignment, _reviewer, _reviewee in rows:
        if assignment.id not in self_ids:
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


def bulk_set_assignment_include(
    db: Session,
    *,
    review_session: ReviewSession,
    assignment_ids: list[int],
    include: bool,
    user: User,
    correlation_id: str,
) -> int:
    """Bulk-set the ``include`` flag on the given assignments,
    scoped to one session — the Assignments-page operator-actions
    card's Inactivate / Activate buttons (Segment 13C).

    Returns the count actually flipped (rows whose previous
    ``include`` differed from ``include``). Audit event
    ``assignments.bulk_include_set`` carries ``counts.flipped`` +
    ``context.include``."""
    if not assignment_ids:
        return 0
    rows = list(
        db.execute(
            select(Assignment).where(
                Assignment.session_id == review_session.id,
                Assignment.id.in_(assignment_ids),
            )
        ).scalars()
    )
    flipped = 0
    for assignment in rows:
        if assignment.include != include:
            assignment.include = include
            flipped += 1
    db.flush()
    audit.write_event(
        db,
        event_type="assignments.bulk_include_set",
        summary=(
            f"{flipped} assignment{'s' if flipped != 1 else ''} bulk-set "
            f"to {'included' if include else 'excluded'}"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(flipped=flipped),
        context={"include": include},
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
        # Project-wide policy: assignments generation NEVER excludes
        # self-reviews at the rule-engine layer. The
        # ``session_rule_sets.exclude_self_reviews`` column is
        # already backfilled / kept at ``False`` by the Band 1
        # save path (see migration ``d2e4f6a8c1b3`` +
        # ``_create_band1_rule_set``); hardcoding here is
        # defence-in-depth so an out-of-band row tweak can't
        # silently re-enable the desugar. Operators who want
        # self-reviews suppressed should either add a Link 2 rule
        # (e.g. ``reviewee.email_or_identifier IS DIFFERENT FROM
        # reviewer.email``) or mark the ``(R, R)`` row inactive on
        # the Assignments page. Spec: ``spec/assignments.md``
        # "Self-review policy".
        options=RuleSetOptions(
            excludeSelfReviews=False,
            seed=row.seed,
        ),
    )


def _full_matrix_schema() -> Any:
    """Synthetic ``RuleSetSchema`` representing the Full Matrix
    default: empty rules, ALL_OF combinator, self-reviews allowed.

    Wave 4 — new-model instruments with untouched Band 1 (both Links
    in ``"all"`` mode) carry ``rule_set_id = NULL``; the engine
    treats this synthetic schema as "no filter," producing every
    (reviewer, reviewee) pair. Legacy instruments with NULL
    ``rule_set_id`` continue to be filtered out upstream — they
    require an explicit pin per Segment 13C.
    """
    from app.schemas.rules import (
        Combinator,
        RuleSetOptions,
        RuleSetSchema,
        RuleSetScope,
    )

    return RuleSetSchema(
        id=0,
        name="Full Matrix (new-model default)",
        description="",
        scope=RuleSetScope.personal,
        combinator=Combinator.ALL_OF,
        rules=[],
        options=RuleSetOptions(excludeSelfReviews=False, seed=0),
    )


@dataclass
class _InstrumentDiff:
    """The reconcile diff for one instrument — see :func:`_diff_one_instrument`."""

    new_pairs: dict[tuple[int, int], tuple[Reviewer, Reviewee, bool]]
    existing_rows: dict[tuple[int, int], Assignment]
    to_insert: set[tuple[int, int]]
    to_delete: set[tuple[int, int]]
    to_keep: set[tuple[int, int]]
    responses_deleted: int
    pairs_count: int
    excluded_counts: dict[str, int]


def _diff_one_instrument(
    db: Session,
    *,
    review_session: ReviewSession,
    instrument: Instrument,
    session_rule_set: SessionRuleSet | None,
    reviewers: list[Reviewer],
    reviewees: list[Reviewee],
    pair_context_lookup: dict[tuple[int, int], Relationship],
    override_exclude_self_reviews: bool | None,
) -> _InstrumentDiff:
    """Run the engine for one instrument and diff its pair fan-out
    against the instrument's existing ``Assignment`` rows.

    Read-only: runs the (pure) rule engine and issues ``SELECT``s, but
    writes nothing. Shared by :func:`_materialise_one_instrument` (which
    then applies the diff) and :func:`reconcile_impact` (which only
    sums the counts for the dry-run).

    ``session_rule_set=None`` is the Full Matrix default — used for
    new-model instruments with untouched Band 1 (Wave 4). The engine
    evaluates a synthetic empty-rules schema and the revision seed
    falls back to ``0``.
    """
    from app.services.rules import engine

    if session_rule_set is None:
        rule_set_schema = _full_matrix_schema()
        revision_seed = 0
    else:
        rule_set_schema = _session_rule_set_to_schema(session_rule_set)
        revision_seed = session_rule_set.id
    result = engine.evaluate(
        rule_set_schema,
        reviewers=reviewers,
        reviewees=reviewees,
        override_exclude_self_reviews=override_exclude_self_reviews,
        revision_seed=revision_seed,
        pair_context_lookup=pair_context_lookup,
    )

    # On a group-scoped instrument, excluding self-reviews rules
    # out the whole group the reviewer is a member of — not just
    # the ``(R, R)`` pair (Segment 13C). Mark each group whose
    # reviewer appears as one of its own reviewees.
    pair_group_key: dict[tuple[int, int], tuple[str, ...]] = {}
    self_review_groups: set[tuple[int, tuple[str, ...]]] = set()
    if instrument.group_kind is not None:
        from app.services import instruments as instruments_service
        from app.services.responses import group_key_for_pair

        boundary = instruments_service.decode_group_kind(
            instrument.group_kind
        )
        for reviewer, reviewee in result.pairs:
            key = group_key_for_pair(
                reviewee=reviewee,
                reviewer_id=reviewer.id,
                reviewee_id=reviewee.id,
                boundary=boundary,
                pair_context_lookup=pair_context_lookup,
            )
            pair_group_key[(reviewer.id, reviewee.id)] = key
            if is_self_review(reviewer, reviewee):
                self_review_groups.add((reviewer.id, key))

    # The engine's pair fan-out, keyed by ``(reviewer_id, reviewee_id)``
    # — the same tuple ``uq_assignment_unique`` enforces.
    new_pairs: dict[tuple[int, int], tuple[Reviewer, Reviewee, bool]] = {}
    for reviewer, reviewee in result.pairs:
        if instrument.group_kind is not None:
            is_self = (
                reviewer.id,
                pair_group_key[(reviewer.id, reviewee.id)],
            ) in self_review_groups
        else:
            is_self = is_self_review(reviewer, reviewee)
        pair_include = (
            review_session.self_reviews_active if is_self else True
        )
        new_pairs[(reviewer.id, reviewee.id)] = (
            reviewer,
            reviewee,
            pair_include,
        )

    existing_rows: dict[tuple[int, int], Assignment] = {
        (row.reviewer_id, row.reviewee_id): row
        for row in db.execute(
            select(Assignment)
            .where(Assignment.session_id == review_session.id)
            .where(Assignment.instrument_id == instrument.id)
        ).scalars()
    }

    new_keys = set(new_pairs)
    existing_keys = set(existing_rows)
    to_insert = new_keys - existing_keys
    to_delete = existing_keys - new_keys
    to_keep = new_keys & existing_keys

    responses_deleted = 0
    if to_delete:
        delete_ids = [existing_rows[key].id for key in to_delete]
        responses_deleted = int(
            db.execute(
                select(func.count(Response.id)).where(
                    Response.assignment_id.in_(delete_ids)
                )
            ).scalar_one()
        )

    return _InstrumentDiff(
        new_pairs=new_pairs,
        existing_rows=existing_rows,
        to_insert=to_insert,
        to_delete=to_delete,
        to_keep=to_keep,
        responses_deleted=responses_deleted,
        pairs_count=len(result.pairs),
        excluded_counts=dict(result.excluded_counts),
    )


def _materialise_one_instrument(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    instrument: Instrument,
    session_rule_set: SessionRuleSet | None,
    reviewers: list[Reviewer],
    reviewees: list[Reviewee],
    pair_context_lookup: dict[tuple[int, int], Relationship],
    mode: AssignmentMode,
    override_exclude_self_reviews: bool | None,
    correlation_id: str,
) -> tuple[int, int]:
    """Materialise ``Assignment`` rows for a single instrument.

    Runs the engine against the instrument's pinned ``SessionRuleSet``,
    then **reconciles** the result against the instrument's existing
    rows: newly eligible pairs are inserted, pairs the rule no longer
    produces are deleted (along with their responses), and pairs
    present before and after are left untouched so their responses
    survive. Emits one ``assignments.generated`` audit event keyed by
    ``refs.instrument_id``.

    Returns ``(deleted, new)`` for this instrument — the ``replaced``
    slot of the ``replace_assignments`` 2-tuple now carries the count
    of pairs removed by the reconcile.
    """
    diff = _diff_one_instrument(
        db,
        review_session=review_session,
        instrument=instrument,
        session_rule_set=session_rule_set,
        reviewers=reviewers,
        reviewees=reviewees,
        pair_context_lookup=pair_context_lookup,
        override_exclude_self_reviews=override_exclude_self_reviews,
    )

    # Drop pairs the rule no longer produces. Their responses go first
    # so the FK constraint holds (the bulk Core ``delete`` bypasses the
    # ORM ``delete-orphan`` cascade — see PR #1065).
    if diff.to_delete:
        delete_ids = [diff.existing_rows[key].id for key in diff.to_delete]
        db.execute(
            delete(Response).where(Response.assignment_id.in_(delete_ids))
        )
        db.execute(delete(Assignment).where(Assignment.id.in_(delete_ids)))

    # Insert newly eligible pairs.
    for key in diff.to_insert:
        reviewer, reviewee, pair_include = diff.new_pairs[key]
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

    # Matched pairs keep their row + responses; only refresh ``include``
    # in place when a ``self_reviews_active`` toggle changed it.
    for key in diff.to_keep:
        _, _, pair_include = diff.new_pairs[key]
        row = diff.existing_rows[key]
        if row.include != pair_include:
            row.include = pair_include
    db.flush()

    # ``Assignment.is_self_review`` is derived from (reviewer / reviewee
    # identifiers + instrument group_kind + relationship boundary tags)
    # — recompute against the post-diff population so newly inserted
    # rows pick up the correct flag and kept rows reflect any
    # composition shift that happened mid-session.
    recompute_self_review_classification(
        db, session_id=review_session.id
    )

    counts_kwargs: dict[str, int] = {
        "new": len(diff.to_insert),
        "deleted": len(diff.to_delete),
        "kept": len(diff.to_keep),
        "responses_deleted": diff.responses_deleted,
        "pairs": diff.pairs_count,
        "instruments": 1,
    }
    for reason, n in diff.excluded_counts.items():
        counts_kwargs[f"excluded_{reason}"] = n
    context: dict[str, str | int | bool] = {"mode": mode.value}
    if override_exclude_self_reviews is not None:
        context["exclude_self_reviews"] = override_exclude_self_reviews
    refs: dict[str, int] = {"instrument_id": instrument.id}
    if session_rule_set is not None:
        refs["rule_set_id"] = session_rule_set.id
    audit.write_event(
        db,
        event_type="assignments.generated",
        summary=(
            f"Reconciled assignments for {instrument.name!r}: "
            f"+{len(diff.to_insert)} new, -{len(diff.to_delete)} removed, "
            f"{len(diff.to_keep)} kept via {mode.value}"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(**counts_kwargs),
        context=context,
        refs=refs,
        correlation_id=correlation_id,
    )
    return len(diff.to_delete), len(diff.to_insert)


@dataclass
class _ReconcileInputs:
    """Read-only inputs a reconcile run needs — see
    :func:`_load_reconcile_inputs`."""

    targets: list[Instrument]
    reviewers: list[Reviewer]
    reviewees: list[Reviewee]
    pair_context_lookup: dict[tuple[int, int], Relationship]
    rule_set_rows: dict[int, SessionRuleSet]

    def rule_set_for(self, instrument: Instrument) -> SessionRuleSet | None:
        # Wave 4 — new-model instruments with untouched Band 1 carry
        # ``rule_set_id = NULL``; the diff/materialise path treats
        # ``None`` as the Full Matrix default. Legacy instruments
        # with NULL ``rule_set_id`` are filtered out upstream in
        # ``_load_reconcile_inputs`` and never reach this method.
        if instrument.rule_set_id is None:
            return None
        rule_set = self.rule_set_rows.get(instrument.rule_set_id)
        if rule_set is None:
            # Dangling FK shouldn't happen given the SET NULL cascade;
            # treat as a data-integrity bug.
            raise ValueError(
                f"instrument {instrument.id} points at missing "
                f"session_rule_set {instrument.rule_set_id}"
            )
        return rule_set


def _load_reconcile_inputs(
    db: Session,
    review_session: ReviewSession,
    instrument_id: int | None,
) -> _ReconcileInputs:
    """Read-only setup shared by :func:`replace_assignments` and
    :func:`reconcile_impact`: resolve the target instruments and load
    the reviewer / reviewee / relationship / rule-set inputs the engine
    needs. Writes nothing.

    ``instrument_id=None`` targets every rule-pinned instrument
    (unpinned ones skipped silently); ``instrument_id=<id>`` targets
    that one instrument and raises ``ValueError`` if it is missing or
    has no rule pinned.
    """
    instruments_query = (
        session_scoped(Instrument, review_session.id)
        .order_by(Instrument.order, Instrument.id)
    )
    if instrument_id is not None:
        instruments_query = instruments_query.where(
            Instrument.id == instrument_id
        )
    all_instruments = list(db.execute(instruments_query).scalars())

    if instrument_id is not None and not all_instruments:
        raise ValueError(
            f"instrument {instrument_id} not found in session "
            f"{review_session.id}"
        )
    # Wave 5 PR 5.3 — every instrument now flows through the same
    # path: NULL ``rule_set_id`` is interpreted as Full Matrix at
    # the diff site via the synthetic empty-rules schema. No more
    # legacy-vs-new-model branching here.
    targets = list(all_instruments)

    reviewers = list_reviewers(db, review_session.id)
    reviewees = list_reviewees(db, review_session.id)
    from app.services import relationships as relationships_service

    pair_context_lookup = relationships_service.pair_context_lookup(
        db, review_session.id
    )

    rule_set_ids = {i.rule_set_id for i in targets if i.rule_set_id is not None}
    rule_set_rows = {
        row.id: row
        for row in db.execute(
            select(SessionRuleSet).where(SessionRuleSet.id.in_(rule_set_ids))
        ).scalars()
    }
    return _ReconcileInputs(
        targets=targets,
        reviewers=reviewers,
        reviewees=reviewees,
        pair_context_lookup=pair_context_lookup,
        rule_set_rows=rule_set_rows,
    )


@dataclass(frozen=True)
class ReconcileImpact:
    """Aggregate dry-run impact of a reconcile across every targeted
    instrument — see :func:`reconcile_impact`."""

    new: int
    deleted: int
    kept: int
    responses_deleted: int


def reconcile_impact(
    db: Session,
    review_session: ReviewSession,
    *,
    instrument_id: int | None = None,
    override_exclude_self_reviews: bool | None = None,
) -> ReconcileImpact:
    """Dry-run the per-instrument reconcile and return the aggregate
    impact a real :func:`replace_assignments` run would have —
    **without writing anything**.

    Drives the workflow super-button's saved-response confirmation:
    ``responses_deleted`` is the number of ``Response`` rows a run
    would delete (responses on pairs the current setup no longer
    produces); ``deleted`` is how many such pairs there are.
    """
    inputs = _load_reconcile_inputs(db, review_session, instrument_id)
    new = deleted = kept = responses_deleted = 0
    for instrument in inputs.targets:
        diff = _diff_one_instrument(
            db,
            review_session=review_session,
            instrument=instrument,
            session_rule_set=inputs.rule_set_for(instrument),
            reviewers=inputs.reviewers,
            reviewees=inputs.reviewees,
            pair_context_lookup=inputs.pair_context_lookup,
            override_exclude_self_reviews=override_exclude_self_reviews,
        )
        new += len(diff.to_insert)
        deleted += len(diff.to_delete)
        kept += len(diff.to_keep)
        responses_deleted += diff.responses_deleted
    return ReconcileImpact(
        new=new,
        deleted=deleted,
        kept=kept,
        responses_deleted=responses_deleted,
    )


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
    inputs = _load_reconcile_inputs(db, review_session, instrument_id)

    if not inputs.targets:
        return 0, 0

    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason="assignments_generated",
        correlation_id=correlation_id,
    )

    total_replaced = 0
    total_new = 0
    for instrument in inputs.targets:
        replaced_here, new_here = _materialise_one_instrument(
            db,
            review_session=review_session,
            user=user,
            instrument=instrument,
            session_rule_set=inputs.rule_set_for(instrument),
            reviewers=inputs.reviewers,
            reviewees=inputs.reviewees,
            pair_context_lookup=inputs.pair_context_lookup,
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
