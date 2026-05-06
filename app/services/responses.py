from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Response,
    ReviewSession,
    Reviewer,
    User,
)
from app.schemas.responses import ResponseUpsert
from app.services import audit

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
    """Validate a non-empty form value against the field's RTD-derived
    ``validation`` block. Returns an error message or None.

    Empty values are treated as "delete the row" by the save layer and
    are not validated here.
    """
    if value == "":
        return None
    validation = field.validation or {}
    data_type = field.data_type
    if data_type in ("Integer", "Decimal"):
        integer = data_type == "Integer"
        try:
            v = int(value) if integer else float(value)
        except ValueError:
            return "Must be a whole number." if integer else "Must be a number."
        min_ = validation.get("min")
        max_ = validation.get("max")
        step = validation.get("step")
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
) -> list[MissingPosition]:
    """List positions where a required field has no Response row.

    The ``position_by_instrument_id`` map drives the page-number prefix
    on the rendered banner; build it once at the call site
    (``submit``) so each MissingPosition entry can land with the page
    number the reviewer needs to navigate to. Iterates assignments
    session-wide (across all instruments the reviewer is assigned on).
    """
    missing: list[MissingPosition] = []
    for assignment in assignments:
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


def _session_position_map(
    db: Session, session_id: int
) -> dict[int, int]:
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == session_id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    return {inst.id: idx + 1 for idx, inst in enumerate(instruments)}


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
    fields_by_instrument = _instrument_fields_by_id(
        db, {a.instrument_id for a in assignments}
    )
    field_index: dict[tuple[int, str], InstrumentResponseField] = {}
    for instrument_id, fields in fields_by_instrument.items():
        for field in fields:
            field_index[(instrument_id, field.field_key)] = field

    valid_upserts, errors = _split_validated(
        upserts=upserts,
        assignment_index=assignment_index,
        field_index=field_index,
        position_by_instrument_id=_session_position_map(db, review_session.id),
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
        session_id=review_session.id,
        detail={
            "session_id": review_session.id,
            "reviewer_id": reviewer.id,
            "count": written,
            "validation_errors": len(errors),
        },
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

    valid_upserts, errors = _split_validated(
        upserts=upserts,
        assignment_index=assignment_index,
        field_index=field_index,
        position_by_instrument_id=position_by_instrument_id,
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
        session_id=review_session.id,
        detail={
            "session_id": review_session.id,
            "reviewer_id": reviewer.id,
            "count": submitted_count,
        },
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
        session_id=review_session.id,
        detail={
            "session_id": review_session.id,
            "reviewer_id": reviewer.id,
            "deleted_count": deleted,
        },
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
        session_id=review_session.id,
        detail={"deleted_count": deleted},
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


def reviewer_session_state(
    db: Session, *, reviewer: Reviewer, session_id: int
) -> ReviewerSessionState:
    assignments = _reviewer_assignments(db, reviewer, session_id)
    if not assignments:
        return ReviewerSessionState(
            total_assignments=0,
            completed_count=0,
            missing_required_count=0,
            required_total=0,
            pill_state="not started",
        )

    fields_by_instrument = _instrument_fields_by_id(
        db, {a.instrument_id for a in assignments}
    )

    any_response = False
    all_required_with_submitted = True
    completed_count = 0
    missing_required_count = 0
    required_total = 0

    for assignment in assignments:
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
        for r in rows:
            if (
                r.submitted_at is None
                and r.response_field_id in required_ids
            ):
                all_required_with_submitted = False

    if not any_response:
        pill_state = "not started"
    elif all_required_with_submitted:
        pill_state = "submitted"
    else:
        pill_state = "in progress"

    return ReviewerSessionState(
        total_assignments=len(assignments),
        completed_count=completed_count,
        missing_required_count=missing_required_count,
        required_total=required_total,
        pill_state=pill_state,
    )


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
    """Total number of Response rows for the session.

    One row per (assignment, response_field). Backs the Extract Data
    card's responses-row count summary.
    """
    return (
        db.execute(
            select(func.count(Response.id))
            .join(Assignment, Response.assignment_id == Assignment.id)
            .where(Assignment.session_id == session_id)
        ).scalar_one()
    )
