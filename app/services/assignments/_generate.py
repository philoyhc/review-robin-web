"""Generation + reconciliation — the rule-runner + Full Matrix +
diff/materialise + reconcile pipeline.

The cohesive `_diff_one_instrument` → `_materialise_one_instrument`
→ `replace_assignments` pipeline, plus the dry-run
`reconcile_impact` that walks the same diff without writing. Also
houses the per-session bulk include toggle
(``bulk_set_assignment_include``) since it shares the audit / commit
shape with the rest of this slice.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

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

from ._coverage import (
    get_or_create_default_instrument,
    list_reviewees,
    list_reviewers,
)
from ._self_review import (
    is_self_review,
    recompute_self_review_classification,
    verify_self_review_classification,
)
from ._shared import _is_active, _is_test_env


_logger = logging.getLogger(__name__)


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

    Note: the pair-level :func:`is_self_review` calls inside this
    function (and its helper :func:`_build_pair_candidates`)
    operate on **unsaved pair candidates** produced by the engine —
    no ``Assignment`` row exists yet, so the column-read shape
    used by every downstream consumer doesn't apply here. The
    whole-group rule is implemented inline against those unsaved
    pairs (lines further down) so the engine's ``include`` /
    exclusion logic still respects ``spec/assignments.md`` §
    *Self-review policy*. Once the rows are written, the regenerate
    path calls :func:`recompute_self_review_classification` to
    populate ``Assignment.is_self_review`` from the canonical
    helper, and :func:`verify_self_review_classification` runs as
    a continuous-gate invariant on the result.

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
    from app.services._queries import session_scoped

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

    # Continuous-gate invariant (PR 4 of
    # ``guide/self_review_consolidate.md``). The per-instrument
    # ``_materialise_one_instrument`` already calls
    # ``recompute_self_review_classification`` after its bulk
    # insert / delete, so post-regenerate the column should match
    # the canonical rule on every row. Drift means a non-regenerate
    # write path is missing a recompute hook, or there's a non-
    # determinism bug in :func:`classify_self_review`.
    drift = verify_self_review_classification(
        db, session_id=review_session.id
    )
    if drift:
        if _is_test_env():
            raise AssertionError(
                "Self-review classification drift detected post-"
                f"regenerate on session {review_session.id}: "
                f"{len(drift)} row(s) differ between "
                "Assignment.is_self_review and "
                "classify_self_review. First few: "
                f"{drift[:5]}. See guide/self_review_consolidate.md."
            )
        # Production: log + auto-correct. The recompute writes the
        # canonical value; the audit-event side already covered the
        # underlying mutation, so the correction is silent.
        _logger.warning(
            "self_review_drift_post_regenerate",
            extra={
                "session_id": review_session.id,
                "drift_count": len(drift),
                "first_few": drift[:5],
            },
        )
        recompute_self_review_classification(
            db, session_id=review_session.id
        )
        db.commit()

    # Lazy-seed pair_context display fields for any populated slots
    # — see guide/unfinished_business item #14.
    from app.services.instruments import seed_display_fields_from_assignments

    if seed_display_fields_from_assignments(db, review_session):
        db.commit()
    return total_replaced, total_new
