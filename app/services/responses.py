from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
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


def save_draft(
    db: Session,
    *,
    review_session: ReviewSession,
    reviewer: Reviewer,
    user: User,
    upserts: list[ResponseUpsert],
    correlation_id: str,
) -> SaveResult:
    """Upsert response rows; empty values delete. Never touches submitted_at."""
    assignments = _reviewer_assignments(db, reviewer, review_session.id)
    assignment_index = {a.id: a for a in assignments}
    fields_by_instrument = _instrument_fields_by_id(
        db, {a.instrument_id for a in assignments}
    )
    field_index: dict[tuple[int, str], InstrumentResponseField] = {}
    for instrument_id, fields in fields_by_instrument.items():
        for field in fields:
            field_index[(instrument_id, field.field_key)] = field

    written = _apply_upserts(
        db,
        upserts=upserts,
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
        },
        correlation_id=correlation_id,
    )
    db.commit()
    return SaveResult(upsert_count=written)


@dataclass
class SubmitResult:
    submitted: bool
    missing: list[MissingPosition]
    submitted_count: int


def submit(
    db: Session,
    *,
    review_session: ReviewSession,
    reviewer: Reviewer,
    user: User,
    upserts: list[ResponseUpsert],
    acknowledge_missing: bool,
    correlation_id: str,
) -> SubmitResult:
    """Persist any pending upserts, validate required fields, then either
    surface a missing-required warning or stamp ``submitted_at = now()``
    on every Response row for this reviewer's assignments.

    The first call with required missing returns ``submitted=False`` and
    writes no audit event. The second call with ``acknowledge_missing``
    set proceeds and writes the audit event with
    ``acknowledged_missing=True``.
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

    _apply_upserts(
        db,
        upserts=upserts,
        assignment_index=assignment_index,
        field_index=field_index,
    )

    # Resolve session-wide page positions so MissingPosition entries
    # carry the page number the reviewer needs to navigate to. Sort
    # mirrors the reviewer surface's Page-N ordering.
    session_instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    position_by_instrument_id = {
        inst.id: idx + 1 for idx, inst in enumerate(session_instruments)
    }

    missing = _compute_missing_required(
        db,
        assignments=assignments,
        fields_by_instrument=fields_by_instrument,
        position_by_instrument_id=position_by_instrument_id,
    )

    if missing and not acknowledge_missing:
        # Persist the draft writes that landed before the missing
        # check; they're useful for the user even on a blocked submit.
        db.commit()
        return SubmitResult(submitted=False, missing=missing, submitted_count=0)

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
            + (f" ({len(missing)} missing)" if missing else "")
        ),
        actor_user_id=user.id,
        session_id=review_session.id,
        detail={
            "session_id": review_session.id,
            "reviewer_id": reviewer.id,
            "count": submitted_count,
            "missing_required_count": len(missing),
            "acknowledged_missing": bool(missing),
        },
        correlation_id=correlation_id,
    )
    db.commit()
    return SubmitResult(
        submitted=True, missing=missing, submitted_count=submitted_count
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
    pill_state: str  # "not started" | "in progress" | "submitted"


def reviewer_session_state(
    db: Session, *, reviewer: Reviewer, session_id: int
) -> ReviewerSessionState:
    assignments = _reviewer_assignments(db, reviewer, session_id)
    if not assignments:
        return ReviewerSessionState(
            total_assignments=0,
            completed_count=0,
            missing_required_count=0,
            pill_state="not started",
        )

    fields_by_instrument = _instrument_fields_by_id(
        db, {a.instrument_id for a in assignments}
    )

    any_response = False
    all_required_with_submitted = True
    completed_count = 0
    missing_required_count = 0

    for assignment in assignments:
        fields = fields_by_instrument.get(assignment.instrument_id, [])
        required_ids = {f.id for f in fields if f.required}
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
