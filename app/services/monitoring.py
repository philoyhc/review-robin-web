"""Per-session monitoring queries used by the operator running-session
pages (Manage Invitations, Responses).

The "incomplete" classification mirrors the criterion locked in
``segment_09_3A.md``: a reviewer is incomplete iff they are not in the
``submitted`` pill state, which collapses both "never opened",
"opened-but-not-submitted", and "submitted-with-warn-override that still
has missing required" into a single bucket.

The reviewee-centric ``per_reviewee_coverage`` (Segment 11C Part 1 PR 3)
classifies reviewees into Complete / Adequate / At risk / No responses
buckets based on the fraction of their assigned reviewers who have
submitted. Thresholds live in ``AT_RISK_THRESHOLDS`` — a single
constant operators can later tune via a session-level setting.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, case, distinct, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Invitation,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services import responses as responses_service


# At-risk classification thresholds for the Responses page. A reviewee
# whose responding-reviewer fraction is at least ``adequate_fraction``
# (but not 100%) renders as "adequate"; below that (and > 0) is
# "at risk"; 0 is "no responses"; 100% is "complete".
AT_RISK_THRESHOLDS = {
    "adequate_fraction": 0.5,
}


# The bucket-set predicates over a coverage / progress state string.
# One source, shared by the service dataclasses here and the view rows
# (``views._responses`` / ``views._invitations``) that carry the same
# state under a different field name (audit V5) — so if a bucket is
# added or renamed, only these move.
def is_at_risk_state(state: str) -> bool:
    """True for the coverage buckets that need operator attention."""
    return state in ("at risk", "no responses")


def is_incomplete_state(state: str) -> bool:
    """True while a reviewer-progress state is anything but submitted."""
    return state != "submitted"


@dataclass
class ReviewerProgress:
    reviewer: Reviewer
    invitation: Invitation | None
    assignment_count: int
    completed_count: int
    missing_required_count: int
    required_total: int
    pill_state: str  # "not started" | "in progress" | "submitted"
    last_reminder_at: object | None  # datetime|None — keep generic for templates

    @property
    def is_incomplete(self) -> bool:
        return is_incomplete_state(self.pill_state)

    @property
    def required_done(self) -> int:
        return self.required_total - self.missing_required_count


def _assigned_active_reviewers(db: Session, session_id: int) -> list[Reviewer]:
    rows = db.execute(
        select(Reviewer)
        .join(Assignment, Assignment.reviewer_id == Reviewer.id)
        .where(
            Assignment.session_id == session_id,
            Assignment.include.is_(True),
            Reviewer.status == "active",
        )
        .distinct()
        .order_by(Reviewer.email)
    ).scalars()
    return list(rows)


def _invitations_by_reviewer(
    db: Session, session_id: int
) -> dict[int, Invitation]:
    rows = db.execute(
        select(Invitation).where(Invitation.session_id == session_id)
    ).scalars()
    return {inv.reviewer_id: inv for inv in rows}


def _plain_instrument_parts(
    db: Session, session_id: int
) -> dict[int, responses_service.RollupParts]:
    """Per-reviewer rollup parts for **per-reviewee instruments**, as one
    aggregate query (19R Item 3 rung 3).

    These are the instruments with no group dedupe to do, which is
    almost all of them and effectively all of the rows. Same two-level
    shape as ``per_reviewee_coverage``: per assignment, then per
    reviewer.

    **The reviewer side's "complete" is not the reviewee side's.** Here
    a required field counts as met when it carries a non-empty value,
    submitted or not; ``submitted_at`` only decides whether the *pill*
    reaches `submitted`. The reviewee side requires both. That
    asymmetry ships, and
    ``tests/integration/test_monitoring_rollup_parity.py`` pins it, so
    it is reproduced here deliberately rather than tidied.
    """
    # ``visible`` is not decoration here. The reviewer surface filters
    # response fields by it (``spec/instruments.md`` § *Visibility + Response
    # fields*), so an un-pinned chip's field is never rendered and
    # cannot be answered — and the Python path this replaces reached
    # its fields through ``_instrument_fields_by_id``, which carries
    # the filter. Without it a reviewer who answered everything they
    # were shown reads `in progress` and both reminder loops keep
    # emailing them. The reviewee rollup does **not** filter, which is
    # its own asymmetry, pinned in the parity file.
    required_per_instrument = (
        select(
            InstrumentResponseField.instrument_id.label("instrument_id"),
            func.count(InstrumentResponseField.id).label("required_total"),
        )
        .where(
            InstrumentResponseField.required.is_(True),
            InstrumentResponseField.visible.is_(True),
        )
        .group_by(InstrumentResponseField.instrument_id)
        .subquery()
    )

    present_required_field = case(
        (
            and_(
                InstrumentResponseField.required.is_(True),
                InstrumentResponseField.visible.is_(True),
                Response.value.is_not(None),
                Response.value != "",
            ),
            Response.response_field_id,
        ),
        else_=None,
    )

    per_assignment = (
        select(
            Assignment.reviewer_id.label("reviewer_id"),
            func.count(Response.id).label("row_count"),
            func.coalesce(
                required_per_instrument.c.required_total, 0
            ).label("required_total"),
            func.count(distinct(present_required_field)).label(
                "present_required"
            ),
            func.count(
                case((Response.submitted_at.is_(None), Response.id), else_=None)
            ).label("unsubmitted_rows"),
        )
        .select_from(Assignment)
        .join(Instrument, Instrument.id == Assignment.instrument_id)
        .outerjoin(Response, Response.assignment_id == Assignment.id)
        .outerjoin(
            InstrumentResponseField,
            InstrumentResponseField.id == Response.response_field_id,
        )
        .outerjoin(
            required_per_instrument,
            required_per_instrument.c.instrument_id
            == Assignment.instrument_id,
        )
        .where(
            Assignment.session_id == session_id,
            Assignment.include.is_(True),
            # The group-scoped ones go down the Python path.
            Instrument.group_kind.is_(None),
        )
        .group_by(
            Assignment.id,
            Assignment.reviewer_id,
            required_per_instrument.c.required_total,
        )
        .subquery()
    )

    missing = per_assignment.c.required_total - per_assignment.c.present_required
    completed = or_(
        and_(
            per_assignment.c.required_total == 0,
            per_assignment.c.row_count > 0,
        ),
        and_(
            per_assignment.c.required_total > 0,
            missing == 0,
        ),
    )

    rows = db.execute(
        select(
            per_assignment.c.reviewer_id,
            func.count().label("total_assignments"),
            func.sum(case((completed, 1), else_=0)).label("completed_count"),
            func.sum(missing).label("missing_required_count"),
            func.sum(per_assignment.c.required_total).label("required_total"),
            func.max(per_assignment.c.row_count).label("max_rows"),
            # Anything unmet or unsubmitted anywhere keeps the pill off
            # `submitted`; summing both and testing for zero is the
            # additive form of the Python loop's two flags.
            func.sum(missing + per_assignment.c.unsubmitted_rows).label(
                "blockers"
            ),
        )
        .group_by(per_assignment.c.reviewer_id)
    ).all()

    return {
        reviewer_id: responses_service.RollupParts(
            total_assignments=int(total_assignments),
            completed_count=int(completed_count),
            missing_required_count=int(missing_required_count),
            required_total=int(required_total),
            any_response=int(max_rows or 0) > 0,
            all_required_and_submitted=int(blockers or 0) == 0,
        )
        for (
            reviewer_id,
            total_assignments,
            completed_count,
            missing_required_count,
            required_total,
            max_rows,
            blockers,
        ) in rows
    }


def _grouped_instrument_parts(
    db: Session, review_session: ReviewSession
) -> dict[int, responses_service.RollupParts]:
    """The same, for **group-scoped instruments**, still in Python.

    The dedupe keeps one assignment per ``(instrument, group_key)``, and
    the key is a tuple of boundary tag values read off the reviewee row
    or an *active* ``Relationship`` — with `(raw or "").strip()` applied
    to each. Reproducing that in SQL means reproducing Python's
    ``strip()``, which trims more than SQL's ``TRIM``, on a path where
    being subtly wrong means an operator's progress figure is subtly
    wrong. The item's open question allowed a hybrid; this is it.

    **The bound is assignments on group-scoped instruments**, not the
    session's assignments. A session that is entirely group-scoped at
    roster scale gains nothing here — stated rather than discovered.
    """
    grouped = list(
        db.execute(
            select(Assignment)
            .join(Instrument, Instrument.id == Assignment.instrument_id)
            .where(
                Assignment.session_id == review_session.id,
                Assignment.include.is_(True),
                Instrument.group_kind.is_not(None),
            )
            .order_by(Assignment.id)
        ).scalars()
    )
    if not grouped:
        return {}

    fields_by_instrument: dict[int, list[InstrumentResponseField]] = {}
    for field in db.execute(
        select(InstrumentResponseField)
        .where(
            InstrumentResponseField.instrument_id.in_(
                {a.instrument_id for a in grouped}
            )
        )
        # Same filter, same reason as the aggregate half above — this
        # stands in for ``_instrument_fields_by_id``, which carries it.
        .where(InstrumentResponseField.visible.is_(True))
        .order_by(InstrumentResponseField.order)
    ).scalars():
        fields_by_instrument.setdefault(field.instrument_id, []).append(field)

    group_key_by_assignment = responses_service.group_keys(
        db, assignments=grouped, session_id=review_session.id
    )
    responses_by_assignment = responses_service.responses_by_assignment(
        db, session_id=review_session.id
    )

    by_reviewer: dict[int, list[Assignment]] = {}
    for assignment in grouped:
        by_reviewer.setdefault(assignment.reviewer_id, []).append(assignment)

    return {
        reviewer_id: responses_service.rollup_parts_from_assignments(
            db,
            rows,
            fields_by_instrument,
            group_key_by_assignment=group_key_by_assignment,
            responses_by_assignment=responses_by_assignment,
        )
        for reviewer_id, rows in by_reviewer.items()
    }


def per_reviewer_progress(
    db: Session, review_session: ReviewSession
) -> list[ReviewerProgress]:
    """Per-reviewer progress rows for the Invitations page.

    **Split by instrument kind** (19R Item 3 rung 3): per-reviewee
    instruments roll up in one aggregate query, group-scoped ones keep
    the Python dedupe, and the two halves add. ``RollupParts`` exists
    for that addition — a pill cannot be summed, because "not started"
    does not say whether the required fields were met.

    Replaces a loop that ran two queries per reviewer and built every
    ``Assignment`` and ``Response`` in the session as ORM objects.

    The pre-rewrite implementation is kept as
    :func:`_per_reviewer_progress_python`, which the parity test runs
    beside this one.
    """
    reviewers = _assigned_active_reviewers(db, review_session.id)
    invitations = _invitations_by_reviewer(db, review_session.id)
    plain = _plain_instrument_parts(db, review_session.id)
    grouped = _grouped_instrument_parts(db, review_session)

    empty = responses_service.RollupParts.empty()
    out: list[ReviewerProgress] = []
    for reviewer in reviewers:
        parts = plain.get(reviewer.id, empty) + grouped.get(reviewer.id, empty)
        invitation = invitations.get(reviewer.id)
        out.append(
            ReviewerProgress(
                reviewer=reviewer,
                invitation=invitation,
                assignment_count=parts.total_assignments,
                completed_count=parts.completed_count,
                missing_required_count=parts.missing_required_count,
                required_total=parts.required_total,
                pill_state=parts.pill_state(),
                last_reminder_at=(
                    invitation.last_reminder_at if invitation else None
                ),
            )
        )
    return out


def _per_reviewer_progress_python(
    db: Session, review_session: ReviewSession
) -> list[ReviewerProgress]:
    """The pre-rewrite implementation, kept as the parity oracle until
    the item closes (19R Item 3 rung 3)."""
    reviewers = _assigned_active_reviewers(db, review_session.id)
    invitations = _invitations_by_reviewer(db, review_session.id)
    # Group keys are computed once for the whole session and passed
    # to each per-reviewer rollup. Computing them inside the loop
    # would re-scan the relationships table once per reviewer.
    all_assignments = list(
        db.execute(
            select(Assignment)
            .options(joinedload(Assignment.reviewee))
            .where(
                Assignment.session_id == review_session.id,
                Assignment.include.is_(True),
            )
        ).scalars()
    )
    group_key_by_assignment = responses_service.group_keys(
        db, assignments=all_assignments, session_id=review_session.id
    )
    # Same idea as the group keys above, for the response rows: one
    # query for the session instead of one per assignment per reviewer.
    responses_by_assignment = responses_service.responses_by_assignment(
        db, session_id=review_session.id
    )
    out: list[ReviewerProgress] = []
    for reviewer in reviewers:
        state = responses_service.reviewer_session_state(
            db,
            reviewer=reviewer,
            session_id=review_session.id,
            group_key_by_assignment=group_key_by_assignment,
            responses_by_assignment=responses_by_assignment,
        )
        invitation = invitations.get(reviewer.id)
        out.append(
            ReviewerProgress(
                reviewer=reviewer,
                invitation=invitation,
                assignment_count=state.total_assignments,
                completed_count=state.completed_count,
                missing_required_count=state.missing_required_count,
                required_total=state.required_total,
                pill_state=state.pill_state,
                last_reminder_at=invitation.last_reminder_at if invitation else None,
            )
        )
    return out


@dataclass
class SummaryCounts:
    assigned: int
    invited: int
    opened: int
    submitted: int
    incomplete: int


def summary_counts(
    db: Session, review_session: ReviewSession
) -> SummaryCounts:
    rows = per_reviewer_progress(db, review_session)
    invited = sum(
        1 for r in rows if r.invitation is not None and r.invitation.status != "pending"
    )
    opened = sum(
        1 for r in rows if r.invitation is not None and r.invitation.status == "opened"
    )
    submitted = sum(1 for r in rows if r.pill_state == "submitted")
    incomplete = sum(1 for r in rows if r.is_incomplete)
    return SummaryCounts(
        assigned=len(rows),
        invited=invited,
        opened=opened,
        submitted=submitted,
        incomplete=incomplete,
    )


@dataclass
class RevieweeCoverage:
    reviewee: Reviewee
    reviewer_count: int
    completed_count: int
    pill_state: str  # "complete" | "adequate" | "at risk" | "no responses"
    last_response_at: datetime | None

    @property
    def is_at_risk(self) -> bool:
        return is_at_risk_state(self.pill_state)


def _classify_coverage(completed: int, total: int) -> str:
    if total == 0 or completed == 0:
        return "no responses"
    if completed == total:
        return "complete"
    fraction = completed / total
    if fraction >= AT_RISK_THRESHOLDS["adequate_fraction"]:
        return "adequate"
    return "at risk"


def _assignment_complete(
    db: Session,
    assignment: Assignment,
    fields: list[InstrumentResponseField],
    responses_by_assignment: dict[int, list["Response"]] | None = None,
) -> tuple[bool, datetime | None]:
    """Returns ``(is_complete, latest_submitted_at)`` for one assignment.

    "Complete" mirrors the reviewer-side definition: every required
    response field has a non-empty value with a non-null ``submitted_at``.
    The second tuple element is the most recent ``submitted_at`` across
    all response rows on the assignment (or ``None``)."""
    if responses_by_assignment is not None:
        rows = responses_by_assignment.get(assignment.id, [])
    else:
        rows = list(
            db.execute(
                select(Response).where(Response.assignment_id == assignment.id)
            ).scalars()
        )
    if not rows:
        return False, None
    required_ids = {f.id for f in fields if f.required}
    by_field = {r.response_field_id: r for r in rows}
    is_complete = True
    if not required_ids:
        is_complete = True  # no required → first response counts as done
    else:
        for fid in required_ids:
            r = by_field.get(fid)
            if r is None or (r.value or "") == "" or r.submitted_at is None:
                is_complete = False
                break
    submitted_times = [r.submitted_at for r in rows if r.submitted_at is not None]
    latest = max(submitted_times) if submitted_times else None
    return is_complete, latest


def per_reviewee_coverage(
    db: Session, review_session: ReviewSession
) -> list[RevieweeCoverage]:
    """Per-reviewee coverage rows for the Responses page.

    **One aggregate query** (19R Item 3 rung 2), in place of loading
    every ``Assignment`` and every ``Response`` in the session as ORM
    objects and counting them in Python — which at a 1,000 x 1,000
    roster meant 408,027 instances for one render
    (``guide/app_responsiveness.md``).

    Two levels of grouping, because "complete" is a property of an
    assignment and the row is a property of a reviewee:

    1. **Per assignment** — how many required fields its instrument has,
       how many of those carry a non-empty *and submitted* answer, how
       many response rows exist at all, and the latest ``submitted_at``
       among them.
    2. **Per reviewee** — how many assignments, how many of them came
       out complete, and the latest stamp across all of them.

    ``uq_response_assignment_field`` is what lets step 1 ask "does a
    satisfying row exist" rather than "is the *last* row satisfying":
    there is at most one row per ``(assignment, response_field)``, so
    the two questions cannot differ.

    Only ``_classify_coverage`` stays in Python, once per reviewee —
    bounded by the roster, not by the assignment count.

    The pre-rewrite implementation is kept as
    :func:`_per_reviewee_coverage_python`, which the parity test runs
    beside this one (``tests/integration/test_monitoring_rollup_parity.py``).
    """
    sid = review_session.id

    # Required-field count per instrument. Its own aggregate rather
    # than a correlated subquery: there are a handful of instruments
    # per session, and an instrument with no required fields must come
    # out as 0 rather than absent — hence the ``coalesce`` below.
    required_per_instrument = (
        select(
            InstrumentResponseField.instrument_id.label("instrument_id"),
            func.count(InstrumentResponseField.id).label("required_total"),
        )
        .where(InstrumentResponseField.required.is_(True))
        .group_by(InstrumentResponseField.instrument_id)
        .subquery()
    )

    #: A response that satisfies its required field: present, non-empty,
    #: and submitted. `CASE` rather than `FILTER` so the same SQL runs
    #: on SQLite and Postgres alike.
    satisfied_field = case(
        (
            and_(
                InstrumentResponseField.required.is_(True),
                Response.value.is_not(None),
                Response.value != "",
                Response.submitted_at.is_not(None),
            ),
            Response.response_field_id,
        ),
        else_=None,
    )

    per_assignment = (
        select(
            Assignment.reviewee_id.label("reviewee_id"),
            func.count(Response.id).label("row_count"),
            func.coalesce(
                required_per_instrument.c.required_total, 0
            ).label("required_total"),
            func.count(distinct(satisfied_field)).label("satisfied"),
            func.max(Response.submitted_at).label("last_at"),
        )
        .select_from(Assignment)
        .outerjoin(Response, Response.assignment_id == Assignment.id)
        .outerjoin(
            InstrumentResponseField,
            InstrumentResponseField.id == Response.response_field_id,
        )
        .outerjoin(
            required_per_instrument,
            required_per_instrument.c.instrument_id
            == Assignment.instrument_id,
        )
        .where(
            Assignment.session_id == sid,
            Assignment.include.is_(True),
        )
        .group_by(
            Assignment.id,
            Assignment.reviewee_id,
            required_per_instrument.c.required_total,
        )
        .subquery()
    )

    # "Complete" mirrors the reviewer-side definition: at least one row
    # exists, and every required field is satisfied. An instrument with
    # no required fields is complete on the strength of any row at all.
    is_complete = and_(
        per_assignment.c.row_count > 0,
        or_(
            per_assignment.c.required_total == 0,
            per_assignment.c.satisfied == per_assignment.c.required_total,
        ),
    )

    rollup = (
        select(
            per_assignment.c.reviewee_id.label("reviewee_id"),
            func.count().label("reviewer_count"),
            func.sum(case((is_complete, 1), else_=0)).label(
                "completed_count"
            ),
            func.max(per_assignment.c.last_at).label("last_response_at"),
        )
        .group_by(per_assignment.c.reviewee_id)
        .subquery()
    )

    rows = db.execute(
        select(
            Reviewee,
            rollup.c.reviewer_count,
            rollup.c.completed_count,
            rollup.c.last_response_at,
        )
        .join(rollup, rollup.c.reviewee_id == Reviewee.id)
        .order_by(Reviewee.email_or_identifier)
    ).all()

    return [
        RevieweeCoverage(
            reviewee=reviewee,
            reviewer_count=int(reviewer_count),
            completed_count=int(completed_count),
            pill_state=_classify_coverage(
                int(completed_count), int(reviewer_count)
            ),
            last_response_at=last_response_at,
        )
        for reviewee, reviewer_count, completed_count, last_response_at in rows
    ]


def _per_reviewee_coverage_python(
    db: Session, review_session: ReviewSession
) -> list[RevieweeCoverage]:
    """The pre-rewrite implementation, kept as the parity oracle.

    19R Item 3 rung 2 replaced :func:`per_reviewee_coverage` with an
    aggregate query. This body stays in the tree, unused by the app,
    until the item closes — it is the thing the new form is checked
    against in ``tests/integration/test_monitoring_rollup_parity.py``,
    and a rewrite with no oracle is a rewrite nobody can check.

    Joins ``reviewees ⨯ assignments ⨯ responses ⨯ instruments``;
    classifies each reviewee per ``AT_RISK_THRESHOLDS``."""
    assignments = list(
        db.execute(
            select(Assignment)
            .where(
                Assignment.session_id == review_session.id,
                Assignment.include.is_(True),
            )
        ).scalars()
    )
    if not assignments:
        return []

    instrument_ids = {a.instrument_id for a in assignments}
    fields_by_instrument: dict[int, list[InstrumentResponseField]] = {}
    if instrument_ids:
        for f in db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id.in_(instrument_ids)
            )
        ).scalars():
            fields_by_instrument.setdefault(f.instrument_id, []).append(f)

    # One query for every response row in the session, in place of one
    # per assignment inside the loop below. 40,404 of the Responses
    # page's 80,432 queries at a 200x200 roster (19K.3).
    responses_by_assignment = responses_service.responses_by_assignment(
        db, session_id=review_session.id
    )

    by_reviewee: dict[int, list[Assignment]] = {}
    for a in assignments:
        by_reviewee.setdefault(a.reviewee_id, []).append(a)

    reviewees = list(
        db.execute(
            select(Reviewee)
            .where(Reviewee.id.in_(by_reviewee.keys()))
            .order_by(Reviewee.email_or_identifier)
        ).scalars()
    )

    out: list[RevieweeCoverage] = []
    for reviewee in reviewees:
        rs = by_reviewee.get(reviewee.id, [])
        completed = 0
        latest: datetime | None = None
        for a in rs:
            fields = fields_by_instrument.get(a.instrument_id, [])
            is_complete, last_at = _assignment_complete(
                db, a, fields, responses_by_assignment
            )
            if is_complete:
                completed += 1
            if last_at is not None and (latest is None or last_at > latest):
                latest = last_at
        pill = _classify_coverage(completed, len(rs))
        out.append(
            RevieweeCoverage(
                reviewee=reviewee,
                reviewer_count=len(rs),
                completed_count=completed,
                pill_state=pill,
                last_response_at=latest,
            )
        )
    return out


__all__ = [
    "AT_RISK_THRESHOLDS",
    "ReviewerProgress",
    "RevieweeCoverage",
    "SummaryCounts",
    "per_reviewer_progress",
    "per_reviewee_coverage",
    "summary_counts",
]
