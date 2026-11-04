"""Read-only tallies over a session's assignments and responses: the
per-reviewer state the dashboard pill and the operator pages read, the
rollup parts, and the response counts (segment 20E rung 1, moved
unchanged from ``_core.py``). Nothing here writes; the save, submit and
recall flow stays in ``_core`` and never calls back into this module.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewer,
)
from app.services.responses._branching import required_field_ids
from app.services.responses._core import _instrument_fields_by_id, _reviewer_assignments
from app.services.responses._group_reconciliation import group_keys


@dataclass
class SessionPill:
    """One reviewer's per-session aggregate state for the dashboard."""

    state: str
    total_assignments: int
    completed_rows: int


@dataclass
class ReviewerSessionState:
    """Aggregate per-reviewer-per-session state.

    Single source of truth shared by the reviewer-dashboard pill
    (``session_pill_for_reviewer``) and the operator monitoring page
    (``monitoring.per_reviewer_progress``). Segment 12 export will read
    the same shape for "incomplete at deadline" cohorts.
    """

    total_assignments: int
    completed_count: int
    missing_required_count: int
    required_total: int
    pill_state: str  # "not started" | "in progress" | "submitted"

    @property
    def required_done(self) -> int:
        return self.required_total - self.missing_required_count


@dataclass
class RollupParts:
    """The additive parts of a reviewer rollup, before a pill is derived.

    ``ReviewerSessionState`` collapses two booleans into `pill_state`,
    which makes it **un-addable**: "not started" does not say whether
    the required fields were unmet, so two halves of one reviewer's work
    cannot be combined through it. 19R Item 3 rung 3 splits the rollup —
    per-reviewee instruments in SQL, group-scoped ones in Python — so
    the halves need a shape that sums.

    ``all_required_and_submitted`` is ``True`` vacuously on an empty
    half, which is what makes it safe to ``and`` two halves together.
    """

    total_assignments: int
    completed_count: int
    missing_required_count: int
    required_total: int
    any_response: bool
    all_required_and_submitted: bool

    @staticmethod
    def empty() -> RollupParts:
        return RollupParts(0, 0, 0, 0, False, True)

    def __add__(self, other: RollupParts) -> RollupParts:
        return RollupParts(
            total_assignments=self.total_assignments + other.total_assignments,
            completed_count=self.completed_count + other.completed_count,
            missing_required_count=(
                self.missing_required_count + other.missing_required_count
            ),
            required_total=self.required_total + other.required_total,
            any_response=self.any_response or other.any_response,
            all_required_and_submitted=(
                self.all_required_and_submitted
                and other.all_required_and_submitted
            ),
        )

    def pill_state(self) -> str:
        """The three-state pill, from the two booleans that carry it."""
        if not self.any_response:
            return "not started"
        if self.all_required_and_submitted:
            return "submitted"
        return "in progress"

    def to_state(self) -> ReviewerSessionState:
        return ReviewerSessionState(
            total_assignments=self.total_assignments,
            completed_count=self.completed_count,
            missing_required_count=self.missing_required_count,
            required_total=self.required_total,
            pill_state=self.pill_state(),
        )


def _state_from_assignments(
    db: Session,
    assignments: list[Assignment],
    fields_by_instrument: dict[int, list[InstrumentResponseField]],
    *,
    group_key_by_assignment: dict[int, tuple[str, ...]] | None = None,
    responses_by_assignment: dict[int, list[Response]] | None = None,
) -> ReviewerSessionState:
    """Inner per-assignment-set rollup shared by
    :func:`reviewer_session_state` (whole-session aggregate) and
    :func:`reviewer_session_state_per_instrument` (per-instrument
    breakdown). The two surfaces share field-set lookup so the
    per-instrument path doesn't double the query count.

    A group-scoped instrument counts **once per group**, not once
    per member: all members of a group carry the same fanned-out
    answer, so only one representative assignment per
    ``(instrument, group_key)`` feeds the totals (Segment 13C
    aggregation contract).

    ``group_key_by_assignment`` may be supplied by a caller that
    already computed it for a wider assignment set (e.g.
    ``per_reviewer_progress`` over every reviewer, or the
    per-instrument breakdown over one reviewer's whole set) — it
    need only cover the assignments passed here. When ``None`` it
    is computed for this set, which scans the relationships table;
    hoisting the call out of a per-reviewer / per-instrument loop
    avoids repeating that scan."""
    return rollup_parts_from_assignments(
        db,
        assignments,
        fields_by_instrument,
        group_key_by_assignment=group_key_by_assignment,
        responses_by_assignment=responses_by_assignment,
    ).to_state()


def rollup_parts_from_assignments(
    db: Session,
    assignments: list[Assignment],
    fields_by_instrument: dict[int, list[InstrumentResponseField]],
    *,
    group_key_by_assignment: dict[int, tuple[str, ...]] | None = None,
    responses_by_assignment: dict[int, list[Response]] | None = None,
) -> RollupParts:
    """:func:`_state_from_assignments` without the pill — see
    :class:`RollupParts` for why a caller would want that.

    This is where the group dedupe and the per-assignment arithmetic
    actually live; the named function above is a thin wrapper that
    derives the pill.
    """
    if not assignments:
        return RollupParts.empty()

    # Collapse each group-scoped instrument's member assignments to
    # one representative — the first by id — so a group response is
    # one unit of work, not N.
    if group_key_by_assignment is None:
        group_key_by_assignment = group_keys(
            db, assignments=assignments, session_id=assignments[0].session_id
        )
    counted: list[Assignment] = []
    seen_groups: set[tuple[int, tuple[str, ...]]] = set()
    for assignment in assignments:
        group_key = group_key_by_assignment.get(assignment.id)
        if group_key is not None:
            marker = (assignment.instrument_id, group_key)
            if marker in seen_groups:
                continue
            seen_groups.add(marker)
        counted.append(assignment)

    any_response = False
    all_required_with_submitted = True
    completed_count = 0
    missing_required_count = 0
    required_total = 0

    for assignment in counted:
        fields = fields_by_instrument.get(assignment.instrument_id, [])
        if responses_by_assignment is not None:
            rows = responses_by_assignment.get(assignment.id, [])
        else:
            rows = list(
                db.execute(
                    select(Response).where(Response.assignment_id == assignment.id)
                ).scalars()
            )
        # 19T Item 11 — per assignment: a required governed field counts
        # only while its branch is open for this row's answers.
        required_ids = required_field_ids(
            fields, {r.response_field_id: r.value for r in rows}
        )
        required_total += len(required_ids)
        if rows:
            any_response = True
        present_required = {
            r.response_field_id for r in rows if (r.value or "") != ""
        }
        row_missing = sum(1 for fid in required_ids if fid not in present_required)
        missing_required_count += row_missing
        if not required_ids:
            if rows:
                completed_count += 1
        elif row_missing == 0:
            completed_count += 1
        if row_missing > 0:
            all_required_with_submitted = False
        # A draft row (submitted_at unset) means this assignment was
        # saved but not submitted. Not gated on required fields — an
        # instrument with only optional fields must not roll up as
        # "submitted" while an unsubmitted draft is outstanding.
        for r in rows:
            if r.submitted_at is None:
                all_required_with_submitted = False

    return RollupParts(
        total_assignments=len(counted),
        completed_count=completed_count,
        missing_required_count=missing_required_count,
        required_total=required_total,
        any_response=any_response,
        all_required_and_submitted=all_required_with_submitted,
    )


def responses_by_assignment(
    db: Session,
    *,
    session_id: int,
    instrument_clause: ColumnElement[bool] | None = None,
) -> dict[int, list[Response]]:
    """Every response row in a session, keyed by assignment id.

    One query where the per-assignment lookup it replaces issues one
    *per assignment*, which is why the pages it serves scaled with the
    **square** of the roster: a reviewer rollup walks every reviewer,
    and each reviewer's assignments are proportional to the roster too.

    Measured 2026-09-12 through the real routes. At 50x50 (2,500
    assignments) that lookup was 2,500 of the Invitations page's 2,633
    queries; at 200x200 (40,000 assignments), rendering Invitations and
    Responses once cost **40,433 and 80,432 queries**. This prefetch
    took both to 434 — linear in the roster rather than quadratic in
    it. 19R Item 3 then removed the loops themselves, so the two pages
    are **35 and 30, flat at every roster size**, and the live budget
    is the table in ``spec/operations_pages.md``, not these figures.
    They are kept because they are why this function exists.

    Joined on ``Assignment.session_id`` rather than an ``in_`` over the
    ids: the id list is the assignment count, which is the thing that
    grows, and SQLite's default variable limit is 999.

    An assignment with no responses is simply absent from the dict, so
    callers use ``.get(id, [])`` and read the same empty list the
    per-assignment query returned.

    ``instrument_clause`` narrows the join to assignments on the
    instruments it matches (a condition over ``Instrument``). The
    rollups' Python halves (``monitoring._python_instrument_parts`` and
    ``monitoring._python_routed_coverage``) need exactly those rows, and
    a session with one such instrument and a roster-scale per-reviewee
    one would otherwise rematerialise every response the aggregate half
    already counted in SQL (19R Item 3 rung 3, Codex P1). Expressed as
    a join rather than an ``in_`` over ids for the same reason the whole
    function is: the id list grows with the assignment count, and
    SQLite's default variable limit is 999.
    """
    stmt = (
        select(Response)
        .join(Assignment, Response.assignment_id == Assignment.id)
        .where(Assignment.session_id == session_id)
    )
    if instrument_clause is not None:
        stmt = stmt.join(
            Instrument, Instrument.id == Assignment.instrument_id
        ).where(instrument_clause)
    rows = db.execute(stmt).scalars()
    out: dict[int, list[Response]] = {}
    for row in rows:
        out.setdefault(row.assignment_id, []).append(row)
    return out


def reviewer_session_state(
    db: Session,
    *,
    reviewer: Reviewer,
    session_id: int,
    group_key_by_assignment: dict[int, tuple[str, ...]] | None = None,
    responses_by_assignment: dict[int, list[Response]] | None = None,
) -> ReviewerSessionState:
    """Whole-session aggregate state. See
    :class:`ReviewerSessionState` for the field shape.

    ``group_key_by_assignment`` is forwarded to
    :func:`_state_from_assignments`; a caller looping over many
    reviewers (``per_reviewer_progress``) passes a session-wide
    map so the relationships scan happens once, not once per
    reviewer. ``responses_by_assignment`` is the same idea for the
    response rows themselves — see :func:`responses_by_assignment`.
    Both default to ``None``, so every caller that does not loop is
    unchanged and still pays one query per assignment."""
    assignments = _reviewer_assignments(db, reviewer, session_id)
    fields_by_instrument = _instrument_fields_by_id(
        db, {a.instrument_id for a in assignments}
    )
    return _state_from_assignments(
        db,
        assignments,
        fields_by_instrument,
        group_key_by_assignment=group_key_by_assignment,
        responses_by_assignment=responses_by_assignment,
    )


def reviewer_session_state_per_instrument(
    db: Session, *, reviewer: Reviewer, session_id: int
) -> dict[int, ReviewerSessionState]:
    """Per-instrument rollup of :func:`reviewer_session_state`,
    keyed by ``instrument_id``. Instruments where the reviewer has
    no active ``Assignment`` rows are absent from the dict; the
    dashboard's per-instrument sub-row builder treats them as
    "no assignments on this instrument" rather than "not started".

    Drives the Segment 15B Slice 6 dashboard per-instrument
    grouping. Single source of truth shared with
    :func:`reviewer_session_state` via the inner
    ``_state_from_assignments`` helper.
    """
    assignments = _reviewer_assignments(db, reviewer, session_id)
    by_instrument: dict[int, list[Assignment]] = {}
    for assignment in assignments:
        by_instrument.setdefault(assignment.instrument_id, []).append(
            assignment
        )
    if not by_instrument:
        return {}
    fields_by_instrument = _instrument_fields_by_id(
        db, set(by_instrument.keys())
    )
    # Compute group keys once over the reviewer's whole assignment
    # set rather than re-scanning the relationships table for each
    # instrument's slice.
    group_key_by_assignment = group_keys(
        db, assignments=assignments, session_id=session_id
    )
    return {
        instrument_id: _state_from_assignments(
            db,
            instr_assignments,
            fields_by_instrument,
            group_key_by_assignment=group_key_by_assignment,
        )
        for instrument_id, instr_assignments in by_instrument.items()
    }


def session_pill_for_reviewer(
    db: Session, *, reviewer: Reviewer, session_id: int
) -> SessionPill:
    """`not started`, `in progress`, or `submitted`."""
    state = reviewer_session_state(db, reviewer=reviewer, session_id=session_id)
    return SessionPill(
        state=state.pill_state,
        total_assignments=state.total_assignments,
        completed_rows=state.completed_count,
    )


def session_response_count(db: Session, session_id: int) -> int:
    """Number of response cells for the session — the Extract Data
    card's row tally, kept in step with ``serialize_responses``.

    A per-reviewee instrument contributes one cell per
    ``(assignment, response_field)``. A group-scoped instrument's
    fanned-out per-member duplicates count **once per group** —
    one cell per ``(reviewer, instrument, group_key,
    response_field)`` (Segment 13C slice D2)."""
    assignments = list(
        db.execute(
            select(Assignment).where(Assignment.session_id == session_id)
        ).scalars()
    )
    group_key_by_assignment = group_keys(
        db, assignments=assignments, session_id=session_id
    )
    if not group_key_by_assignment:
        return db.execute(
            select(func.count(Response.id))
            .join(Assignment, Response.assignment_id == Assignment.id)
            .where(Assignment.session_id == session_id)
        ).scalar_one()

    assignment_index = {a.id: a for a in assignments}
    seen: set[tuple[int, int, tuple[str, ...], int]] = set()
    count = 0
    for assignment_id, field_id in db.execute(
        select(Response.assignment_id, Response.response_field_id)
        .join(Assignment, Response.assignment_id == Assignment.id)
        .where(Assignment.session_id == session_id)
    ):
        group_key = group_key_by_assignment.get(assignment_id)
        if group_key is None:
            count += 1
            continue
        assignment = assignment_index[assignment_id]
        cell = (
            assignment.reviewer_id,
            assignment.instrument_id,
            group_key,
            field_id,
        )
        if cell not in seen:
            seen.add(cell)
            count += 1
    return count
