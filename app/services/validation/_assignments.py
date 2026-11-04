"""The rules on assignments: included pairs, a reviewer with none, an
instrument with none. Segment 20E rung 4b, moved unchanged from
``validation.py``.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Reviewee,
    Reviewer,
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
    "_active_assignment_presence",
    "_active_reviewers",
    "_check_assignments_instrument_empty",
    "_check_assignments_no_included_pairs",
    "_check_assignments_reviewer_missing",
    "_check_assignments_reviewer_missing_for_instrument",
    "_included_instrument_ids",
]


def _check_assignments_no_included_pairs(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    """Session-wide warning: zero included rows across every
    instrument.

    Replaces the retired ``assignments.no_mode`` rule (which fired
    only when ``assignment_mode`` was NULL). The successor catches
    a strictly broader case — sessions where Generate ran but every
    row is currently ``include=False`` (e.g. self-reviews bulk-
    deactivated on every instrument), and sessions that never
    generated at all. Either way reviewers would see an empty
    surface.

    Per-instrument detail rides on the
    ``instruments.zero_included`` warning.
    """
    if sum(inputs.included_count_by_instrument.values()) == 0:
        yield ValidationIssue(
            severity=Severity.warning,
            source="assignments",
            message=(
                "No included assignment rows on any instrument — "
                "reviewers will see an empty surface"
            ),
        )


def _active_assignment_presence(
    db: Session, session_id: int
) -> set[tuple[int, int]]:
    """``(instrument_id, reviewer_id)`` for every row that gives an
    active reviewer work: included, with both sides active.

    Status is read here rather than trusted from ``include``, which is
    only recomputed at Prepare (findings B2): a person deactivated
    since then still has ``include=True`` rows until the next one, and
    Validate should already say what that Prepare will leave (B4).
    """
    return {
        (instrument_id, reviewer_id)
        for instrument_id, reviewer_id in db.execute(
            select(Assignment.instrument_id, Assignment.reviewer_id)
            .join(Reviewer, Reviewer.id == Assignment.reviewer_id)
            .join(Reviewee, Reviewee.id == Assignment.reviewee_id)
            .where(
                Assignment.session_id == session_id,
                Assignment.include.is_(True),
                Reviewer.status == "active",
                Reviewee.status == "active",
            )
            .distinct()
        ).all()
    }


def _included_instrument_ids(inputs: ValidationInputs) -> set[int]:
    """Instruments with at least one ``include=True`` row, read off the
    same ``included_count_by_instrument`` snapshot that
    ``assignments.no_included_pairs`` and ``instruments.zero_included``
    use, so the per-reviewer rules stand down on exactly the
    instruments those siblings report."""
    return {
        instrument_id
        for instrument_id, count in inputs.included_count_by_instrument.items()
        if count
    }


def _active_reviewers(inputs: ValidationInputs) -> list[Reviewer]:
    return [r for r in inputs.reviewers if r.status == "active"]


def _check_assignments_reviewer_missing(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    """Single-instrument sessions: every **active** reviewer must have
    at least one included assignment on an active reviewee (findings
    B4). A row that exists but is excluded, or points at an inactive
    reviewee, gives them nothing to do, and they are skipped for
    invitations rather than warned about. An inactive reviewer is not
    checked: they are meant to have no work.

    Skipped when ``assignment_mode is None`` — a session that has
    never been Generated has no actionable per-reviewer breakdown,
    and surfacing every-reviewer-missing on top of the
    ``assignments.no_included_pairs`` warning would double up the
    noise. (``instruments.no_rule_pinned`` was named here too
    until Wave 5 PR 5.3 retired it; it is inert and raises
    nothing.) Also skipped on multi-instrument sessions — the
    per-instrument rule
    (``assignments.reviewer_missing_for_instrument``) carries the
    breakdown there.
    """
    if review_session.assignment_mode is None:
        return
    if len(inputs.instruments) != 1:
        return
    if not _included_instrument_ids(inputs):
        # Nothing is included at all: ``assignments.no_included_pairs``
        # reports it once, rather than once per reviewer.
        return
    with_work = {
        reviewer_id
        for _, reviewer_id in _active_assignment_presence(
            db, review_session.id
        )
    }
    for reviewer in _active_reviewers(inputs):
        if reviewer.id in with_work:
            continue
        yield ValidationIssue(
            severity=Severity.warning,
            source="assignments",
            field=f"reviewer_id:{reviewer.id}",
            message=(
                f"Reviewer {reviewer.name!r} ({reviewer.email}) has no "
                "active assignments"
            ),
            # No anchor: the fix is Generate on the Assignments page,
            # which has no per-reviewer row to land on. The
            # ``reviewer-row-`` ids live on the Reviewers page only.
        )


def _check_assignments_reviewer_missing_for_instrument(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    """Multi-instrument sessions: every **active** reviewer must have
    at least one included assignment on an active reviewee on each
    instrument (findings B4; the single-instrument sibling says why).

    Skipped on single-instrument sessions (the sibling
    ``assignments.reviewer_missing`` rule covers those without the
    per-instrument breakdown). Skipped when ``assignment_mode is
    None`` — a never-generated session has no actionable
    per-reviewer breakdown. Per-instrument issues are suppressed for
    an instrument with no included row — the sibling
    ``assignments.instrument_empty`` and ``instruments.zero_included``
    rules report that instrument instead, by the same test, so the
    operator sees one issue per empty instrument rather than
    (reviewers × instruments) duplicated noise. An instrument whose
    included rows all have an inactive side is not suppressed: no
    sibling reports it, so each active reviewer is named.
    """
    if review_session.assignment_mode is None:
        return
    if len(inputs.instruments) <= 1:
        return
    presence: dict[int, set[int]] = {
        i.id: set() for i in inputs.instruments
    }
    for instrument_id, reviewer_id in _active_assignment_presence(
        db, review_session.id
    ):
        if instrument_id in presence:
            presence[instrument_id].add(reviewer_id)
    included = _included_instrument_ids(inputs)
    active = _active_reviewers(inputs)
    for instrument in inputs.instruments:
        if instrument.id not in included:
            # Sibling rules report an instrument with nothing included.
            continue
        in_use = presence[instrument.id]
        for reviewer in active:
            if reviewer.id in in_use:
                continue
            yield ValidationIssue(
                severity=Severity.warning,
                source="assignments",
                field=(
                    f"reviewer_id:{reviewer.id}"
                    f"|instrument_id:{instrument.id}"
                ),
                message=(
                    f"Reviewer {reviewer.name!r} ({reviewer.email}) "
                    f"has no active assignments on the "
                    f"{_instrument_label(instrument)!r} instrument"
                ),
                fix_anchor=f"#instrument-{instrument.id}",
            )


def _check_assignments_instrument_empty(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    """Multi-instrument sessions: every instrument must have at
    least one ``Assignment`` row.

    Skipped on single-instrument sessions (the session-wide
    ``assignments.no_included_pairs`` warning + per-instrument
    ``instruments.zero_included`` warning cover the no-rows case
    without needing the multi-instrument breakdown). Skipped when
    ``assignment_mode is None`` for the same reason.
    """
    if review_session.assignment_mode is None:
        return
    if len(inputs.instruments) <= 1:
        return
    instrument_ids_with_rows = {
        row[0]
        for row in db.execute(
            select(Assignment.instrument_id)
            .where(Assignment.session_id == review_session.id)
            .distinct()
        ).all()
    }
    for instrument in inputs.instruments:
        if instrument.id in instrument_ids_with_rows:
            continue
        yield ValidationIssue(
            severity=Severity.warning,
            source="assignments",
            field=f"instrument_id:{instrument.id}",
            message=(
                f"Instrument {_instrument_label(instrument)!r} has "
                "no assignments — reviewers won't see this page"
            ),
            fix_anchor=f"#instrument-{instrument.id}",
        )
