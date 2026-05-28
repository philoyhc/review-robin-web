from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    InstrumentResponseField,
    Response,
    ReviewSession,
    Reviewer,
    User,
)
from app.schemas.responses import ResponseUpsert
from app.services import audit
from app.services.responses._group_reconciliation import (
    _expand_group_upserts,
    _group_instrument_ids,
    _group_key_by_assignment,
    _session_position_map,
    group_keys,
)

_FORM_FIELD_PATTERN = re.compile(r"^response\[(?P<aid>\d+)\]\[(?P<key>[^\]]+)\]$")


def parse_form_payload(form: Mapping[str, str]) -> list[ResponseUpsert]:
    """Extract ``response[aid][field_key]=value`` entries from a form mapping.

    Non-matching keys are ignored. Whitespace-only values are normalised
    to empty strings; the save layer interprets empty as "delete the row".
    """
    out: list[ResponseUpsert] = []
    for key, value in form.items():
        match = _FORM_FIELD_PATTERN.match(key)
        if match is None:
            continue
        out.append(
            ResponseUpsert(
                assignment_id=int(match["aid"]),
                field_key=match["key"],
                value=(value or "").strip(),
            )
        )
    return out


@dataclass
class MissingPosition:
    assignment_id: int
    field_key: str
    field_label: str
    reviewee_name: str
    # Session-wide page number (1-based) the assignment's instrument
    # sits at, so the missing-required banner can prefix entries with
    # ``Page N:``. Resolved from ``(Instrument.order, Instrument.id)``
    # at submit time. Per-PR-ε of Segment 11D follow-on.
    position: int


@dataclass
class ValidationError:
    assignment_id: int
    field_key: str
    field_label: str
    reviewee_name: str
    value: str
    message: str
    position: int


_STEP_TOLERANCE = 1e-6


def _format_number(v: float, *, integer: bool) -> str:
    if integer:
        return str(int(v))
    if v == int(v):
        return f"{v:.1f}"
    return f"{v:g}"


def validate_value(
    field: InstrumentResponseField, value: str
) -> str | None:
    """Validate a non-empty form value against the field's inline
    type + bounds (Wave 3 PR ii — reads ``_inline_*`` directly per
    locked decision 11; the ``validation`` JSON cache stays for now
    but is no longer the source of truth for this code path).
    Returns an error message or None.

    Empty values are treated as "delete the row" by the save layer
    and are not validated here.
    """
    if value == "":
        return None
    data_type = field.data_type
    if data_type in ("Integer", "Decimal"):
        integer = data_type == "Integer"
        try:
            v = int(value) if integer else float(value)
        except ValueError:
            return "Must be a whole number." if integer else "Must be a number."
        min_ = field._inline_min
        max_ = field._inline_max
        step = field._inline_step
        if min_ is not None and v < min_:
            return f"Must be at least {_format_number(min_, integer=integer)}."
        if max_ is not None and v > max_:
            return f"Must be at most {_format_number(max_, integer=integer)}."
        if step is not None and step > 0:
            anchor = min_ if min_ is not None else 0
            offset = (v - anchor) / step
            if abs(offset - round(offset)) > _STEP_TOLERANCE:
                return (
                    "Must be in increments of "
                    f"{_format_number(step, integer=integer)}."
                )
        return None
    if data_type == "String":
        # ``_inline_max`` doubles as the char-length cap for String
        # fields (per the model column comment + decision 11).
        max_length = field._inline_max
        if max_length is not None and len(value) > int(max_length):
            return f"Must be at most {int(max_length)} characters."
        return None
    if data_type == "List":
        options_csv = field._inline_list_csv or ""
        options = [opt.strip() for opt in options_csv.split(",") if opt.strip()]
        if options and value not in options:
            return "Must be one of the listed options."
        return None
    return None


def _reviewer_assignments(
    db: Session, reviewer: Reviewer, session_id: int
) -> list[Assignment]:
    """Active (include=true) assignments for this reviewer in this session."""
    stmt = (
        select(Assignment)
        .where(
            Assignment.session_id == session_id,
            Assignment.reviewer_id == reviewer.id,
            Assignment.include.is_(True),
        )
        .order_by(Assignment.id)
    )
    return list(db.execute(stmt).scalars())


def _instrument_fields_by_id(
    db: Session, instrument_ids: set[int]
) -> dict[int, list[InstrumentResponseField]]:
    if not instrument_ids:
        return {}
    stmt = (
        select(InstrumentResponseField)
        .where(InstrumentResponseField.instrument_id.in_(instrument_ids))
        .where(InstrumentResponseField.visible.is_(True))
        .order_by(InstrumentResponseField.order)
    )
    by_instrument: dict[int, list[InstrumentResponseField]] = {}
    for field in db.execute(stmt).scalars():
        by_instrument.setdefault(field.instrument_id, []).append(field)
    return by_instrument


def _apply_upserts(
    db: Session,
    *,
    upserts: list[ResponseUpsert],
    assignment_index: dict[int, Assignment],
    field_index: dict[tuple[int, str], InstrumentResponseField],
) -> int:
    """Upsert / delete Response rows. Returns number of upserts that wrote a row."""
    written = 0
    for u in upserts:
        assignment = assignment_index.get(u.assignment_id)
        if assignment is None:
            continue
        field = field_index.get((assignment.instrument_id, u.field_key))
        if field is None:
            continue
        existing = db.execute(
            select(Response).where(
                Response.assignment_id == assignment.id,
                Response.response_field_id == field.id,
            )
        ).scalar_one_or_none()
        if u.value == "":
            if existing is not None:
                db.delete(existing)
            continue
        if existing is None:
            db.add(
                Response(
                    assignment_id=assignment.id,
                    response_field_id=field.id,
                    value=u.value,
                )
            )
        else:
            existing.value = u.value
        written += 1
    db.flush()
    return written


def _compute_missing_required(
    db: Session,
    *,
    assignments: list[Assignment],
    fields_by_instrument: dict[int, list[InstrumentResponseField]],
    position_by_instrument_id: dict[int, int],
    group_key_by_assignment: dict[int, tuple[str, ...]],
) -> list[MissingPosition]:
    """List positions where a required field has no Response row.

    The ``position_by_instrument_id`` map drives the page-number prefix
    on the rendered banner; build it once at the call site
    (``submit``) so each MissingPosition entry can land with the page
    number the reviewer needs to navigate to. Iterates assignments
    session-wide (across all instruments the reviewer is assigned on).

    For a group-scoped instrument the reviewer answers once per group
    (one surface row), so only the first member assignment of each
    ``(instrument, group_key)`` is reported — a missing field surfaces
    once per group, not once per member.
    """
    missing: list[MissingPosition] = []
    seen_groups: set[tuple[int, tuple[str, ...]]] = set()
    for assignment in assignments:
        group_key = group_key_by_assignment.get(assignment.id)
        if group_key is not None:
            marker = (assignment.instrument_id, group_key)
            if marker in seen_groups:
                continue
            seen_groups.add(marker)
        fields = fields_by_instrument.get(assignment.instrument_id, [])
        required = [f for f in fields if f.required]
        if not required:
            continue
        rows = list(
            db.execute(
                select(Response).where(Response.assignment_id == assignment.id)
            ).scalars()
        )
        present_field_ids = {r.response_field_id for r in rows if (r.value or "") != ""}
        for field in required:
            if field.id in present_field_ids:
                continue
            missing.append(
                MissingPosition(
                    assignment_id=assignment.id,
                    field_key=field.field_key,
                    field_label=field.label,
                    reviewee_name=assignment.reviewee.name,
                    position=position_by_instrument_id.get(
                        assignment.instrument_id, 0
                    ),
                )
            )
    # Sort by (position, reviewee_name, field_label) so the rendered
    # banner reads top-to-bottom in the same order the reviewer can
    # walk the pages — Page 1 entries first, then Page 2, etc.
    missing.sort(
        key=lambda m: (m.position, m.reviewee_name, m.field_label)
    )
    return missing


def compute_row_completion(
    db: Session, assignment: Assignment
) -> tuple[bool, int, datetime | None]:
    """Return (is_complete, missing_required_count, latest_submitted_at)
    for a single assignment row.

    is_complete is True when every required field on the assignment's
    instrument has a non-empty Response row.
    """
    fields = list(
        db.execute(
            select(InstrumentResponseField)
            .where(InstrumentResponseField.instrument_id == assignment.instrument_id)
            .where(InstrumentResponseField.visible.is_(True))
            .order_by(InstrumentResponseField.order)
        ).scalars()
    )
    required = [f for f in fields if f.required]
    rows = list(
        db.execute(
            select(Response).where(Response.assignment_id == assignment.id)
        ).scalars()
    )
    present_field_ids = {r.response_field_id for r in rows if (r.value or "") != ""}
    missing = sum(1 for f in required if f.id not in present_field_ids)
    submitted_ats = [r.submitted_at for r in rows if r.submitted_at is not None]
    latest = max(submitted_ats) if submitted_ats else None
    return missing == 0, missing, latest


@dataclass
class SaveResult:
    upsert_count: int
    errors: list[ValidationError]


def _split_validated(
    *,
    upserts: list[ResponseUpsert],
    assignment_index: dict[int, Assignment],
    field_index: dict[tuple[int, str], InstrumentResponseField],
    position_by_instrument_id: dict[int, int],
) -> tuple[list[ResponseUpsert], list[ValidationError]]:
    """Partition upserts into (valid, errors) by running ``validate_value``
    against each. Upserts that target an unknown assignment / field key are
    treated as valid here — ``_apply_upserts`` already silently drops them."""
    valid: list[ResponseUpsert] = []
    errors: list[ValidationError] = []
    for u in upserts:
        assignment = assignment_index.get(u.assignment_id)
        if assignment is None:
            valid.append(u)
            continue
        field = field_index.get((assignment.instrument_id, u.field_key))
        if field is None:
            valid.append(u)
            continue
        message = validate_value(field, u.value)
        if message is None:
            valid.append(u)
            continue
        errors.append(
            ValidationError(
                assignment_id=assignment.id,
                field_key=field.field_key,
                field_label=field.label,
                reviewee_name=assignment.reviewee.name,
                value=u.value,
                message=message,
                position=position_by_instrument_id.get(
                    assignment.instrument_id, 0
                ),
            )
        )
    errors.sort(key=lambda e: (e.position, e.reviewee_name, e.field_label))
    return valid, errors


def save_draft(
    db: Session,
    *,
    review_session: ReviewSession,
    reviewer: Reviewer,
    user: User,
    upserts: list[ResponseUpsert],
    correlation_id: str,
) -> SaveResult:
    """Upsert response rows; empty values delete. Never touches submitted_at.

    Values that fail RTD-level validation (Integer / Decimal range and
    step) are skipped — only valid upserts are persisted. The caller
    surfaces the error list so the offending fields can be re-rendered
    with the typed value still in the box."""
    assignments = _reviewer_assignments(db, reviewer, review_session.id)
    assignment_index = {a.id: a for a in assignments}
    group_instrument_ids = _group_instrument_ids(
        db, {a.instrument_id for a in assignments}
    )
    group_key_by_assignment = _group_key_by_assignment(
        db,
        assignments=assignments,
        group_instrument_ids=group_instrument_ids,
        session_id=review_session.id,
    )
    fields_by_instrument = _instrument_fields_by_id(
        db, {a.instrument_id for a in assignments}
    )
    field_index: dict[tuple[int, str], InstrumentResponseField] = {}
    for instrument_id, fields in fields_by_instrument.items():
        for field in fields:
            field_index[(instrument_id, field.field_key)] = field

    # Validate the raw upserts first — a group-scoped instrument's
    # surface posts one upsert per group (keyed to a representative
    # member), so a bad value yields one error, not one per member.
    valid_upserts, errors = _split_validated(
        upserts=upserts,
        assignment_index=assignment_index,
        field_index=field_index,
        position_by_instrument_id=_session_position_map(db, review_session.id),
    )
    # Then fan the valid upserts out to every member of their group.
    valid_upserts = _expand_group_upserts(
        valid_upserts,
        assignments=assignments,
        group_instrument_ids=group_instrument_ids,
        group_key_by_assignment=group_key_by_assignment,
    )

    written = _apply_upserts(
        db,
        upserts=valid_upserts,
        assignment_index=assignment_index,
        field_index=field_index,
    )

    audit.write_event(
        db,
        event_type="responses.saved",
        summary=f"Saved {written} response{'' if written == 1 else 's'} (draft)",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(
            assignments_touched=len({u.assignment_id for u in upserts}),
            responses_saved=written,
        ),
        refs={"reviewer_id": reviewer.id},
        correlation_id=correlation_id,
    )
    db.commit()
    return SaveResult(upsert_count=written, errors=errors)


@dataclass
class SubmitResult:
    submitted: bool
    missing: list[MissingPosition]
    errors: list[ValidationError]
    submitted_count: int


def submit(
    db: Session,
    *,
    review_session: ReviewSession,
    reviewer: Reviewer,
    user: User,
    upserts: list[ResponseUpsert],
    correlation_id: str,
) -> SubmitResult:
    """Persist any pending upserts, validate required fields, then either
    block on missing-required or stamp ``submitted_at = now()`` on every
    Response row for this reviewer's assignments.

    Submit is a hard gate: any missing required field anywhere in the
    session blocks submission. Drafts written via ``upserts`` still
    commit on a blocked submit so the reviewer's typed values aren't
    lost. There is no acknowledge-and-submit-anyway path — the
    reviewer must fill the missing fields (or remove their value
    elsewhere if the operator has already loosened a ``required``
    constraint) before the submit can land.
    """
    assignments = _reviewer_assignments(db, reviewer, review_session.id)
    assignment_index = {a.id: a for a in assignments}
    group_instrument_ids = _group_instrument_ids(
        db, {a.instrument_id for a in assignments}
    )
    group_key_by_assignment = _group_key_by_assignment(
        db,
        assignments=assignments,
        group_instrument_ids=group_instrument_ids,
        session_id=review_session.id,
    )
    fields_by_instrument = _instrument_fields_by_id(
        db, {a.instrument_id for a in assignments}
    )
    field_index: dict[tuple[int, str], InstrumentResponseField] = {}
    for instrument_id, fields in fields_by_instrument.items():
        for field in fields:
            field_index[(instrument_id, field.field_key)] = field

    # Resolve session-wide page positions so MissingPosition / ValidationError
    # entries carry the page number the reviewer needs to navigate to.
    position_by_instrument_id = _session_position_map(db, review_session.id)

    # Validate the raw upserts before fanning group answers out, so a
    # bad value on a group-scoped instrument yields one error rather
    # than one per member.
    valid_upserts, errors = _split_validated(
        upserts=upserts,
        assignment_index=assignment_index,
        field_index=field_index,
        position_by_instrument_id=position_by_instrument_id,
    )
    valid_upserts = _expand_group_upserts(
        valid_upserts,
        assignments=assignments,
        group_instrument_ids=group_instrument_ids,
        group_key_by_assignment=group_key_by_assignment,
    )

    _apply_upserts(
        db,
        upserts=valid_upserts,
        assignment_index=assignment_index,
        field_index=field_index,
    )

    if errors:
        # Persist the valid draft writes; surface the bad ones so the
        # reviewer can fix and retry without losing their other typing.
        db.commit()
        return SubmitResult(
            submitted=False, missing=[], errors=errors, submitted_count=0
        )

    missing = _compute_missing_required(
        db,
        assignments=assignments,
        fields_by_instrument=fields_by_instrument,
        position_by_instrument_id=position_by_instrument_id,
        group_key_by_assignment=group_key_by_assignment,
    )

    if missing:
        # Persist the draft writes that landed before the missing
        # check; they're useful for the user even on a blocked submit.
        db.commit()
        return SubmitResult(
            submitted=False, missing=missing, errors=[], submitted_count=0
        )

    now = datetime.now(timezone.utc)
    submitted_count = 0
    for assignment in assignments:
        rows = list(
            db.execute(
                select(Response).where(Response.assignment_id == assignment.id)
            ).scalars()
        )
        for row in rows:
            row.submitted_at = now
            submitted_count += 1
    db.flush()

    audit.write_event(
        db,
        event_type="responses.submitted",
        summary=(
            f"Submitted {submitted_count} response{'' if submitted_count == 1 else 's'}"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(submitted=submitted_count),
        refs={"reviewer_id": reviewer.id},
        correlation_id=correlation_id,
    )
    db.commit()
    return SubmitResult(
        submitted=True,
        missing=missing,
        errors=[],
        submitted_count=submitted_count,
    )


@dataclass
class RecallResult:
    recalled_count: int


def recall(
    db: Session,
    *,
    review_session: ReviewSession,
    reviewer: Reviewer,
    user: User,
    correlation_id: str,
) -> RecallResult:
    """Roll back a fully-submitted session to draft for one reviewer.

    Nulls ``submitted_at`` on every Response row belonging to the
    reviewer's assignments in this session — saved values are
    preserved. Pre-conditions are checked by the route layer
    (session must be ``ready``); this service trusts the caller.

    Idempotent: zero rows-already-submitted is a no-op that
    still writes an audit event so the operator can see the
    intent in the log. Driver of the reviewer summary page's
    "Recall my submission" button.
    """
    assignments = _reviewer_assignments(db, reviewer, review_session.id)
    recalled_count = 0
    for assignment in assignments:
        rows = list(
            db.execute(
                select(Response).where(Response.assignment_id == assignment.id)
            ).scalars()
        )
        for row in rows:
            if row.submitted_at is not None:
                row.submitted_at = None
                recalled_count += 1
    db.flush()
    audit.write_event(
        db,
        event_type="responses.recalled",
        summary=(
            f"Recalled {recalled_count} submission"
            f"{'' if recalled_count == 1 else 's'}"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(recalled=recalled_count),
        refs={"reviewer_id": reviewer.id},
        correlation_id=correlation_id,
    )
    db.commit()
    return RecallResult(recalled_count=recalled_count)


@dataclass
class ClearResult:
    deleted_count: int


def clear_all(
    db: Session,
    *,
    review_session: ReviewSession,
    reviewer: Reviewer,
    user: User,
    correlation_id: str,
) -> ClearResult:
    """Delete every Response row for this reviewer's assignments in the session."""
    assignments = _reviewer_assignments(db, reviewer, review_session.id)
    deleted = 0
    for assignment in assignments:
        rows = list(
            db.execute(
                select(Response).where(Response.assignment_id == assignment.id)
            ).scalars()
        )
        for row in rows:
            db.delete(row)
            deleted += 1
    db.flush()

    audit.write_event(
        db,
        event_type="responses.cleared",
        summary=f"Cleared {deleted} response{'' if deleted == 1 else 's'}",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(deleted=deleted),
        refs={"reviewer_id": reviewer.id},
        correlation_id=correlation_id,
    )
    db.commit()
    return ClearResult(deleted_count=deleted)


@dataclass
class DeleteAllResult:
    deleted_count: int


def delete_all_for_session(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str,
) -> DeleteAllResult:
    """Delete every Response row for the session in one transaction.

    Preserves reviewers, reviewees, assignments, instruments, invitations.
    Allowed in any session status (operator-driven wipe of response data
    only). Emits a single ``responses.deleted_all`` audit event.
    """
    assignment_ids = list(
        db.execute(
            select(Assignment.id).where(
                Assignment.session_id == review_session.id
            )
        ).scalars()
    )
    deleted = 0
    if assignment_ids:
        rows = list(
            db.execute(
                select(Response).where(
                    Response.assignment_id.in_(assignment_ids)
                )
            ).scalars()
        )
        for row in rows:
            db.delete(row)
            deleted += 1
        db.flush()

    audit.write_event(
        db,
        event_type="responses.deleted_all",
        summary=f"Deleted {deleted} response{'' if deleted == 1 else 's'} (operator)",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(deleted=deleted),
        correlation_id=correlation_id,
    )
    db.commit()
    return DeleteAllResult(deleted_count=deleted)


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


def _state_from_assignments(
    db: Session,
    assignments: list[Assignment],
    fields_by_instrument: dict[int, list[InstrumentResponseField]],
    *,
    group_key_by_assignment: dict[int, tuple[str, ...]] | None = None,
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
    if not assignments:
        return ReviewerSessionState(
            total_assignments=0,
            completed_count=0,
            missing_required_count=0,
            required_total=0,
            pill_state="not started",
        )

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
        required_ids = {f.id for f in fields if f.required}
        required_total += len(required_ids)
        rows = list(
            db.execute(
                select(Response).where(Response.assignment_id == assignment.id)
            ).scalars()
        )
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

    if not any_response:
        pill_state = "not started"
    elif all_required_with_submitted:
        pill_state = "submitted"
    else:
        pill_state = "in progress"

    return ReviewerSessionState(
        total_assignments=len(counted),
        completed_count=completed_count,
        missing_required_count=missing_required_count,
        required_total=required_total,
        pill_state=pill_state,
    )


def reviewer_session_state(
    db: Session,
    *,
    reviewer: Reviewer,
    session_id: int,
    group_key_by_assignment: dict[int, tuple[str, ...]] | None = None,
) -> ReviewerSessionState:
    """Whole-session aggregate state. See
    :class:`ReviewerSessionState` for the field shape.

    ``group_key_by_assignment`` is forwarded to
    :func:`_state_from_assignments`; a caller looping over many
    reviewers (``per_reviewer_progress``) passes a session-wide
    map so the relationships scan happens once, not once per
    reviewer."""
    assignments = _reviewer_assignments(db, reviewer, session_id)
    fields_by_instrument = _instrument_fields_by_id(
        db, {a.instrument_id for a in assignments}
    )
    return _state_from_assignments(
        db,
        assignments,
        fields_by_instrument,
        group_key_by_assignment=group_key_by_assignment,
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
