"""Self-review classification — the canonical helpers + the
recompute invariant + the breakdown reporters.

Single canonical computation surface (per
``guide/self_review_consolidate.md``). Every write site (Assignment
creation / fan-out / recompute) and the PR-1 backfill route through
:func:`classify_self_review` so the rule lives in exactly one place.
"""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import audit


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

    Pair-level — operates on the unsaved reviewer × reviewee
    population, before any ``Assignment`` row exists. The whole-
    group rule from ``spec/assignments.md`` § *Self-review policy*
    only applies once assignments are materialised (since groups
    are keyed off ``Assignment.instrument_id`` / ``group_kind``);
    a pair count over the unsaved matrix is the right semantics
    here.
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
    """Count saved Assignment rows that are self-reviews per the
    canonical whole-group rule (``spec/assignments.md`` § *Self-
    review policy*).

    Reads ``Assignment.is_self_review`` directly — the column is
    the source of truth (PR 3 of
    ``guide/self_review_consolidate.md``). Pre-consolidation this
    summed over a pair-level ``is_self_review(reviewer, reviewee)``
    check, silently missing the non-``(R, R)`` member rows of
    self-review groups on group-scoped instruments.
    """
    return (
        db.execute(
            select(func.count(Assignment.id)).where(
                Assignment.session_id == session_id,
                Assignment.is_self_review.is_(True),
            )
        ).scalar_one()
    )


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


def verify_self_review_classification(
    db: Session, *, session_id: int
) -> list[tuple[int, bool, bool]]:
    """Read-only sanity check: return the list of assignment rows
    in the session whose stored ``is_self_review`` column differs
    from what :func:`classify_self_review` now computes.

    Each entry is ``(assignment_id, stored_value, expected_value)``.
    An empty list means the column is in sync with the canonical
    rule for every row.

    Used by :func:`replace_assignments` as a post-recompute
    continuous-gate invariant — drift means either a write path
    forgot to call :func:`recompute_self_review_classification`,
    or there's a non-determinism bug in the helper. In test envs
    (``PYTEST_CURRENT_TEST`` set) the regenerate path asserts on
    drift; in production it logs and auto-corrects. See
    ``guide/self_review_consolidate.md``.
    """
    rows = db.execute(
        select(Assignment, Reviewer, Reviewee)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        .where(Assignment.session_id == session_id)
    ).all()
    if not rows:
        return []
    classification = classify_self_review(
        db, session_id=session_id, rows=rows
    )
    return [
        (assignment.id, assignment.is_self_review, expected)
        for assignment, _, _ in rows
        for expected in (classification[assignment.id],)
        if assignment.is_self_review != expected
    ]


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

    "Self-review assignment" is group-aware — every
    member-assignment in a group whose reviewer is themselves a
    member counts (see ``spec/assignments.md`` § *Self-review
    policy*). Reads the canonical ``Assignment.is_self_review``
    column directly. Instruments with none are absent from the
    dict.
    """
    rows = db.execute(
        select(Assignment).where(
            Assignment.session_id == session_id,
            Assignment.is_self_review.is_(True),
        )
    ).scalars().all()
    out: dict[int, tuple[int, int]] = {}
    for assignment in rows:
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
    # Read the canonical column to pick self-review rows on this
    # instrument. The column is the source of truth post-
    # consolidation (PR 1/2 of ``guide/self_review_consolidate.md``).
    rows = db.execute(
        select(Assignment).where(
            Assignment.session_id == review_session.id,
            Assignment.instrument_id == instrument_id,
            Assignment.is_self_review.is_(True),
        )
    ).scalars().all()
    flipped = 0
    for assignment in rows:
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
