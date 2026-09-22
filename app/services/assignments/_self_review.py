"""Self-review classification — the canonical helpers + the
recompute invariant + the breakdown reporters.

Single canonical computation surface (per
``guide/archive/self_review_consolidate.md``). The rule body is
:func:`classify_self_review_pairs`; every write site (Assignment
creation / fan-out / recompute) and the PR-1 backfill reach it, either
directly or through the entity-shaped :func:`classify_self_review`
adapter, so the rule lives in exactly one place.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import NamedTuple

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import audit
from app.services.email_identity import normalize_email


def is_self_review(reviewer: Reviewer, reviewee: Reviewee) -> bool:
    return _is_self_review_pair(
        reviewer.email, reviewee.email_or_identifier
    )


def _is_self_review_pair(
    reviewer_email: str, reviewee_identifier: str
) -> bool:
    """The pair-level test on the two strings it actually reads.

    Split out of :func:`is_self_review` for the column-tuple path in
    :func:`recompute_self_review_classification`, which projects
    ``Reviewer.email`` rather than loading the entity. The rule is
    unchanged: a reviewee identified by something other than an email
    address can never be a self-review, and the comparison is over
    ``normalize_email`` on both sides.
    """
    if "@" not in reviewee_identifier:
        return False
    return normalize_email(reviewer_email) == normalize_email(
        reviewee_identifier
    )


class AssignmentPair(NamedTuple):
    """The projection of an assignment row that the self-review rule
    and the group-key computation actually read.

Seven slots, traced 19S Item 3: the group key needs ``id``,
    ``instrument_id``, ``reviewer_id``, ``reviewee_id`` and the
    ``Reviewee`` (boundary tags are read off it); the pair test needs
    the reviewer's email; and ``is_self_review`` carries the **stored**
    value so the recompute can report how many rows it changed without
    re-reading them. (Six is the count of ``Assignment`` attributes the
    two passes read; this class also carries a ``Reviewer`` column, so
    the two figures are not the same one.)

    Deliberately duck-compatible with ``Assignment`` on the five
    attributes ``app.services.responses.group_keys`` reads, so that
    function takes either shape unchanged.

    ``Reviewee`` stays an entity rather than a tag projection because
    the boundary spec names its fields dynamically
    (``group_key_for_pair`` does ``getattr(reviewee, source_field)``).
    It costs little: the ORM dedupes by primary key, so a session with
    200 reviewees builds 200 instances however many assignment rows
    join to them.
    """

    id: int
    instrument_id: int
    reviewer_id: int
    reviewee_id: int
    reviewer_email: str
    reviewee: Reviewee
    is_self_review: bool


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

    Entity-shaped adapter over :func:`classify_self_review_pairs`,
    which holds the rule. Callers that already have the three entities
    keep this signature; the recompute, which projects columns rather
    than loading an ``Assignment`` per row (19S Item 3), calls the pair
    form directly. Either way the rule is stated once — see
    ``guide/archive/self_review_consolidate.md``.

    Note the adapter is not free: it builds one
    :class:`AssignmentPair` per row on top of whatever entities the
    caller already loaded. On ``verify_self_review_classification``,
    the whole-session pass 19S Item 3 deliberately left alone, that is
    ~40 ms at the 200 x 200 bench against a 13 s Prepare.
    """
    return classify_self_review_pairs(
        db,
        session_id=session_id,
        pairs=[
            AssignmentPair(
                id=assignment.id,
                instrument_id=assignment.instrument_id,
                reviewer_id=assignment.reviewer_id,
                reviewee_id=assignment.reviewee_id,
                reviewer_email=reviewer.email,
                reviewee=reviewee,
                is_self_review=assignment.is_self_review,
            )
            for assignment, reviewer, reviewee in rows
        ],
    )


def classify_self_review_pairs(
    db: Session,
    *,
    session_id: int,
    pairs: Sequence[AssignmentPair],
) -> dict[int, bool]:
    """The canonical self-review rule, over :class:`AssignmentPair`
    projections rather than entities.

    This is where the rule lives; :func:`classify_self_review` is the
    entity-shaped adapter over it. Returns
    ``{assignment_id: is_self_review}`` for every pair passed in. The
    two branches are documented on that function.
    """
    from app.services.responses import group_keys

    group_key_by_assignment = group_keys(
        db, assignments=pairs, session_id=session_id
    )
    # (group instrument, reviewer) -> group key of the group that
    # reviewer is a member of (i.e. groups where the (R, R) member
    # pair exists, identifying the group as a self-review group).
    self_group_key: dict[tuple[int, int], tuple[str, ...]] = {}
    for pair in pairs:
        if pair.id in group_key_by_assignment and _is_self_review_pair(
            pair.reviewer_email, pair.reviewee.email_or_identifier
        ):
            self_group_key[(pair.instrument_id, pair.reviewer_id)] = (
                group_key_by_assignment[pair.id]
            )
    result: dict[int, bool] = {}
    for pair in pairs:
        group_key = group_key_by_assignment.get(pair.id)
        if group_key is None:
            # Individual-scoped instrument.
            result[pair.id] = _is_self_review_pair(
                pair.reviewer_email, pair.reviewee.email_or_identifier
            )
        else:
            # Group-scoped: whole-group rule.
            result[pair.id] = (
                self_group_key.get((pair.instrument_id, pair.reviewer_id))
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

    **Column tuples in, one bulk statement out** (19S Item 3). This
    pass runs once per instrument inside a regenerate and used to
    re-materialize the whole session as ``(Assignment, Reviewer,
    Reviewee)`` entities — at the 200 x 200 bench, 80,000 objects per
    call for the sake of one boolean each. It now selects the
    :class:`AssignmentPair` projection and writes the rows that
    changed as a single ORM bulk UPDATE keyed by primary key. The
    ``Reviewer`` / ``Reviewee`` joins stay because the rule reads them;
    only the ``Assignment`` entity is gone.
    """
    pairs = [
        AssignmentPair(
            id=row_id,
            instrument_id=instrument_id,
            reviewer_id=reviewer_id,
            reviewee_id=reviewee_id,
            reviewer_email=reviewer_email,
            reviewee=reviewee,
            is_self_review=bool(stored),
        )
        for (
            row_id,
            instrument_id,
            reviewer_id,
            reviewee_id,
            stored,
            reviewer_email,
            reviewee,
        ) in db.execute(
            select(
                Assignment.id,
                Assignment.instrument_id,
                Assignment.reviewer_id,
                Assignment.reviewee_id,
                Assignment.is_self_review,
                Reviewer.email,
                Reviewee,
            )
            .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
            .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
            .where(Assignment.session_id == session_id)
        ).all()
    ]
    if not pairs:
        return 0
    classification = classify_self_review_pairs(
        db, session_id=session_id, pairs=pairs
    )
    changed = [
        {"id": pair.id, "is_self_review": classification[pair.id]}
        for pair in pairs
        if pair.is_self_review != classification[pair.id]
    ]
    if changed:
        # ORM bulk UPDATE by primary key. Unlike the bulk *insert* in
        # ``_materialise_one_instrument``, this form keeps the identity
        # map in step: an ``Assignment`` the session already holds sees
        # the new value without a reload, which is what lets
        # ``verify_self_review_classification`` keep reading entities.
        # SQLAlchemy is pinned only as ``>=2.0``, so that behaviour is
        # asserted rather than assumed — see
        # ``tests/unit/test_recompute_self_review_bulk_update.py``.
        db.execute(update(Assignment), changed)
        db.flush()
    return len(changed)


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
