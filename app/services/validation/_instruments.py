"""The rules on instruments: fields, display fields, rule sets and
whether generated assignments are stale. Segment 20E rung 4b, moved unchanged from
``validation.py``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    ReviewSession,
)
from app.schemas.validation import Severity, ValidationIssue
from app.services.instruments import _instrument_label
from app.services.validation._inputs import (
    ValidationInputs,
)

# What the package's other modules import from this one; the leading
# underscore marks a name private to the package, not to the module.
__all__ = [
    "_check_instruments_no_display_fields",
    "_check_instruments_no_fields",
    "_check_instruments_no_rule_pinned",
    "_check_instruments_rule_set_unloadable",
    "_check_instruments_stale_generated",
    "_check_instruments_zero_included",
    "_check_new_model_no_visible_response_fields",
    "_staleness",
]


def _check_instruments_no_fields(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    for instrument in inputs.instruments:
        if instrument.id not in inputs.instruments_with_response_fields:
            label = (
                instrument.description.strip()
                if instrument.description and instrument.description.strip()
                else _instrument_label(instrument)
            )
            yield ValidationIssue(
                severity=Severity.error,
                source="instruments",
                message=f"Instrument '{label}' has no response fields",
                fix_anchor=f"#instrument-{instrument.id}",
            )


def _check_instruments_no_rule_pinned(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    """Wave 5 PR 5.3 — retired. Pre-PR-5.3 the rule fired on legacy
    instruments with NULL ``rule_set_id``. With the legacy /
    new-model split collapsed, an instrument with no stored Band 1
    rule evaluates as Full Matrix (Wave 4 PR 1), so a NULL
    ``rule_set_id`` is not a setup gap in itself. Readiness is
    checked elsewhere: ``instruments.no_visible_response_fields``
    here, and the Band 1 "Not set" gate
    (``instruments.is_configured``), which the Workflow card
    enforces off-validate. The rule key stays registered so audit
    history remains addressable.
    """
    return
    yield  # pragma: no cover — make this an Iterable


def _check_new_model_no_visible_response_fields(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    """Warning per new-model instrument with no ``visible=True``
    :class:`InstrumentResponseField` rows once the session has
    reviewers + reviewees.

    Without a visible response field, the reviewer surface renders
    zero rows on the instrument's tab even though assignments exist
    (Wave 4 PR 2 — replaces the rule-set-pinned readiness gap for
    new-model instruments).
    """
    if not inputs.reviewers or not inputs.reviewees:
        return
    for instrument in inputs.instruments:
        if instrument.id in inputs.instruments_with_visible_response_fields:
            continue
        yield ValidationIssue(
            severity=Severity.warning,
            source="instruments",
            message=(
                f"Instrument {_instrument_label(instrument)!r} has no "
                "visible response fields — reviewers see an empty page. "
                "Select at least one response-field chip on the "
                "instrument's card."
            ),
            fix_anchor=f"#instrument-{instrument.id}",
        )


def _staleness(
    db: Session, review_session: ReviewSession, inputs: ValidationInputs
) -> Mapping[int, Any]:
    """``staleness_by_instrument`` once per run: the unloadable and the
    stale checks both read it, and each call reloads the rosters and
    re-stamps every instrument."""
    if "staleness" not in inputs._memo:
        from app.services import assignments as assignments_service

        inputs._memo["staleness"] = assignments_service.staleness_by_instrument(db, review_session)
    return inputs._memo["staleness"]


def _check_instruments_rule_set_unloadable(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    """``instruments.rule_set_unloadable`` — one error per instrument
    whose stored rule set the engine can't load (findings E4,
    2026-10-22). Generate would fail on it, so Prepare can't pass; the
    Band 1 card's Save rebuilds the rules from what it shows, once a
    rule it refuses to keep is removed."""
    state_by_instrument = _staleness(db, review_session, inputs)
    for instrument in inputs.instruments:
        state = state_by_instrument.get(instrument.id)
        if state is None or state.load_error is None:
            continue
        yield ValidationIssue(
            severity=Severity.error,
            source="instruments",
            message=(
                f"{_instrument_label(instrument)}'s assignment "
                f"rule can't be loaded ({state.load_error}). Change or "
                f"remove that rule in its Instrument assignment rule, then "
                f"Save."
            ),
            fix_anchor=f"#instrument-{instrument.id}",
        )


def _check_instruments_stale_generated(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    """Warning per instrument whose materialized rows have fallen out of
    step with what the engine would produce now.

    The criterion is the first sentence, and it has two halves: the
    instrument has materialized rows, and a reconcile run would insert
    or delete at least one pair. The two situations this rule's ``why``
    names are the ones an operator recognizes — the pinned rule
    changed, or the rosters or relationships moved after Generate —
    but they are not exhaustive: the instrument's own ``group_kind``
    moves the verdict too, whenever the pinned rule set excludes
    self-reviews, because the group boundary decides which pairs that
    exclusion drops. The instrument's ``self_reviews_active`` (the
    Self review toggle, findings E3) does **not**, despite reading
    like it would: it sets a pair's
    ``include`` flag, and the diff is a difference of pair *keys*.

    The verdict is the engine's own diff
    (``assignments.staleness_by_instrument``). Since 19R Item 2 that
    diff may be served from a stamped cache rather than recomputed, so
    it agrees with what Generate would do **under the conditions**
    ``spec/assignments.md`` § *Staleness* states — the stamp covering
    every input the diff reads, and Generate writing the fresh verdict
    through. Stating it unconditionally is what that item's close
    deliberately stopped doing.

    **An instrument that has never generated is not flagged**, and the
    engine decides that rather than this check: staleness means
    materialized rows that have fallen out of step, which needs rows to
    have been materialized. An always-stale badge on a fresh session is
    the failure mode that retired the previous signal. The Workflow
    card's Generate step and the ``assignments.*`` empty rules carry
    that case instead.

    **This rule was a registered no-op between Wave 5 PR 5.1 and Segment
    19N.** Its predecessor compared per-rule eligible counts via a helper
    that retired with the operator-library tier, and the replacement was
    judged unnecessary because "the Workflow card + Generate button
    already cover the *operator pinned a rule but never generated*
    case" — which is not one of the two situations the ``why`` names, so
    both of them were covered by nothing while the rule stayed in the
    registry with a fix link. *A check that returns nothing reports a
    clean bill on exactly the thing it exists to catch*, which is worse
    than its absence, because the operator reads the silence as an
    answer.
    """
    state_by_instrument = _staleness(db, review_session, inputs)
    if not any(state.stale for state in state_by_instrument.values()):
        return
    for instrument in inputs.instruments:
        state = state_by_instrument.get(instrument.id)
        if state is None or not state.stale:
            continue
        yield ValidationIssue(
            severity=Severity.warning,
            source="instruments",
            message=(
                f"Instrument {_instrument_label(instrument)!r} would "
                f"change if assignments were regenerated — re-Generate "
                f"to refresh the pairs"
            ),
            fix_anchor=f"#instrument-{instrument.id}",
        )


def _check_instruments_zero_included(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    """Warning per instrument with ``generated_count > 0`` but
    ``included_count == 0``.

    Typical cause: the operator bulk-deactivated every row on the
    instrument (e.g. flipping the Self review chip off on a
    self-review-only instrument). Reviewers will land on the
    instrument's page and see nothing.

    Instruments that never generated are silent here — the sibling
    ``assignments.instrument_empty`` / ``assignments.no_included_pairs``
    rules cover the no-rows-at-all case.
    """
    from app.services import assignments as assignments_service

    # Only one check needs the generated counts, so they stay a live
    # read here rather than joining `ValidationInputs`. Note the
    # asymmetry that creates: `generated` is read now, `included` was
    # snapshotted at the top of the run. They agree because a report
    # run never touches `assignments` rows — the one write in it is
    # `staleness_by_instrument` caching its verdict onto instruments —
    # and a check that broke that would have to say so here.
    generated_by_instrument = assignments_service.existing_count_per_instrument(
        db, review_session.id
    )
    for instrument in inputs.instruments:
        generated = generated_by_instrument.get(instrument.id, 0)
        included = inputs.included_count_by_instrument.get(instrument.id, 0)
        if generated > 0 and included == 0:
            yield ValidationIssue(
                severity=Severity.warning,
                source="instruments",
                message=(
                    f"Instrument {_instrument_label(instrument)!r} has "
                    f"{generated} generated row"
                    f"{'' if generated == 1 else 's'} but none are "
                    "included — reviewers won't see this page"
                ),
                fix_anchor=f"#instrument-{instrument.id}",
            )


def _check_instruments_no_display_fields(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    for instrument in inputs.instruments:
        if instrument.id not in inputs.instruments_with_response_fields:
            # The no_fields rule already covers this; skip.
            continue
        if instrument.id not in inputs.instruments_with_display_fields:
            label = (
                instrument.description.strip()
                if instrument.description and instrument.description.strip()
                else _instrument_label(instrument)
            )
            yield ValidationIssue(
                severity=Severity.warning,
                source="instruments",
                message=(
                    f"Instrument '{label}' has no display fields — reviewer pages will be sparse"
                ),
                fix_anchor=f"#instrument-{instrument.id}",
            )
