from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Assignment,
    Instrument,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.schemas.assignments import AssignmentMode, ManualAssignmentRow
from app.schemas.validation import Severity, ValidationIssue
from app.services import audit

PAIR_PREVIEW_LIMIT = 200

MANUAL_CSV_MAX_BYTES = 1 * 1024 * 1024
MANUAL_CSV_MAX_ROWS = 5000

_TRUTHY = {"true", "yes", "1"}
_FALSY = {"false", "no", "0"}


def reviewee_fields_with_data(db: Session, session_id: int) -> list[str]:
    """Friendly names of reviewee columns that hold at least one value."""
    labels: list[str] = []
    has_any = (
        db.execute(
            select(Reviewee.id).where(Reviewee.session_id == session_id).limit(1)
        ).first()
        is not None
    )
    if has_any:
        labels.extend(["Name", "Email"])
    profile_found = db.execute(
        select(Reviewee.id)
        .where(Reviewee.session_id == session_id)
        .where(Reviewee.profile_link.is_not(None))
        .where(Reviewee.profile_link != "")
        .limit(1)
    ).first()
    if profile_found is not None:
        labels.append("Profile")
    for slot, friendly in ((1, "Tag 1"), (2, "Tag 2"), (3, "Tag 3")):
        col = getattr(Reviewee, f"tag_{slot}")
        found = db.execute(
            select(Reviewee.id)
            .where(Reviewee.session_id == session_id)
            .where(col.is_not(None))
            .where(col != "")
            .limit(1)
        ).first()
        if found is not None:
            labels.append(friendly)
    return labels


def reviewer_fields_with_data(db: Session, session_id: int) -> list[str]:
    """Friendly names of reviewer columns that hold at least one value."""
    labels: list[str] = []
    has_any = (
        db.execute(
            select(Reviewer.id).where(Reviewer.session_id == session_id).limit(1)
        ).first()
        is not None
    )
    if has_any:
        labels.extend(["Name", "Email"])
    for slot, friendly in ((1, "Tag 1"), (2, "Tag 2"), (3, "Tag 3")):
        col = getattr(Reviewer, f"tag_{slot}")
        found = db.execute(
            select(Reviewer.id)
            .where(Reviewer.session_id == session_id)
            .where(col.is_not(None))
            .where(col != "")
            .limit(1)
        ).first()
        if found is not None:
            labels.append(friendly)
    return labels


def display_source_presence(db: Session, session_id: int) -> dict[str, bool]:
    """Which Display-Fields source codes have at least one non-empty value.

    Reviewer.Name and Reviewee.Email are mandatory and always considered
    present. Tag1..3 inspect the reviewee rows; PairContext1..3 and
    AssignmentContext1..3 inspect the JSON ``context`` blob on assignments.
    """
    presence: dict[str, bool] = {
        "Reviewer.Name": True,
        "Reviewee.Email": True,
    }
    for slot in (1, 2, 3):
        col = getattr(Reviewee, f"tag_{slot}")
        found = db.execute(
            select(Reviewee.id)
            .where(Reviewee.session_id == session_id)
            .where(col.is_not(None))
            .where(col != "")
            .limit(1)
        ).first()
        presence[f"Reviewee.Tag{slot}"] = found is not None

    pair_present = {1: False, 2: False, 3: False}
    asgn_present = {1: False, 2: False, 3: False}
    for (ctx,) in db.execute(
        select(Assignment.context).where(Assignment.session_id == session_id)
    ).all():
        if not ctx:
            continue
        for slot in (1, 2, 3):
            if ctx.get(f"pair_context_{slot}"):
                pair_present[slot] = True
            if ctx.get(f"assignment_context_{slot}"):
                asgn_present[slot] = True
    for slot in (1, 2, 3):
        presence[f"PairContext{slot}"] = pair_present[slot]
        presence[f"AssignmentContext{slot}"] = asgn_present[slot]
    return presence


@dataclass
class ManualParseResult:
    rows: list[ManualAssignmentRow]
    issues: list[ValidationIssue]

    @property
    def is_blocked(self) -> bool:
        return any(i.is_blocking for i in self.issues)


def _parse_include(value: str) -> tuple[bool | None, str | None]:
    """Returns (parsed, error_message). Empty string defaults to True."""
    stripped = value.strip()
    if not stripped:
        return True, None
    lowered = stripped.lower()
    if lowered in _TRUTHY:
        return True, None
    if lowered in _FALSY:
        return False, None
    return None, f"IncludeAssignment '{stripped}' is not a recognised true/false value"


def _is_active(row: Reviewer | Reviewee) -> bool:
    return (row.status or "active") == "active"


def parse_manual_csv(
    content: bytes,
    reviewers: list[Reviewer],
    reviewees: list[Reviewee],
) -> ManualParseResult:
    source = "assignments"
    issues: list[ValidationIssue] = []

    if len(content) > MANUAL_CSV_MAX_BYTES:
        return ManualParseResult(
            rows=[],
            issues=[
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    message=f"File too large (max {MANUAL_CSV_MAX_BYTES // 1024} KiB)",
                )
            ],
        )
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return ManualParseResult(
            rows=[],
            issues=[
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    message="File is not valid UTF-8",
                )
            ],
        )

    reader = csv.DictReader(io.StringIO(text))
    fieldnames = list(reader.fieldnames or [])
    if not fieldnames:
        return ManualParseResult(
            rows=[],
            issues=[
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    message="CSV has no header row",
                )
            ],
        )

    for required in ("ReviewerEmail", "RevieweeEmail"):
        if required not in fieldnames:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    field=required,
                    message=f"Missing required column: {required}",
                )
            )
    if issues:
        return ManualParseResult(rows=[], issues=issues)

    raw_rows = list(reader)
    if len(raw_rows) > MANUAL_CSV_MAX_ROWS:
        return ManualParseResult(
            rows=[],
            issues=[
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    message=f"Too many rows (max {MANUAL_CSV_MAX_ROWS})",
                )
            ],
        )

    reviewer_by_email = {
        r.email.casefold(): r for r in reviewers if _is_active(r)
    }
    reviewee_by_ident = {
        r.email_or_identifier.casefold(): r for r in reviewees if _is_active(r)
    }
    inactive_reviewer_emails = {
        r.email.casefold() for r in reviewers if not _is_active(r)
    }
    inactive_reviewee_idents = {
        r.email_or_identifier.casefold() for r in reviewees if not _is_active(r)
    }

    parsed: list[ManualAssignmentRow] = []
    seen_pairs: dict[tuple[int, int], int] = {}

    for index, raw in enumerate(raw_rows, start=1):
        reviewer_email = (raw.get("ReviewerEmail") or "").strip()
        reviewee_identifier = (raw.get("RevieweeEmail") or "").strip()

        if not reviewer_email:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="ReviewerEmail",
                    message="ReviewerEmail is required",
                )
            )
            continue
        if not reviewee_identifier:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="RevieweeEmail",
                    message="RevieweeEmail is required",
                )
            )
            continue

        reviewer = reviewer_by_email.get(reviewer_email.casefold())
        if reviewer is None:
            if reviewer_email.casefold() in inactive_reviewer_emails:
                message = (
                    f"Inactive reviewer: '{reviewer_email}' is in this "
                    f"session's reviewer roster but is not active"
                )
            else:
                message = (
                    f"Unknown reviewer: '{reviewer_email}' is not in this "
                    f"session's reviewer roster"
                )
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="ReviewerEmail",
                    message=message,
                )
            )
            continue
        reviewee = reviewee_by_ident.get(reviewee_identifier.casefold())
        if reviewee is None:
            if reviewee_identifier.casefold() in inactive_reviewee_idents:
                message = (
                    f"Inactive reviewee: '{reviewee_identifier}' is in this "
                    f"session's reviewee roster but is not active"
                )
            else:
                message = (
                    f"Unknown reviewee: '{reviewee_identifier}' is not in "
                    f"this session's reviewee roster"
                )
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="RevieweeEmail",
                    message=message,
                )
            )
            continue

        pair_key = (reviewer.id, reviewee.id)
        if pair_key in seen_pairs:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    message=(
                        f"Duplicate assignment: '{reviewer_email}' -> "
                        f"'{reviewee_identifier}' (also on row {seen_pairs[pair_key]})"
                    ),
                )
            )
            continue
        seen_pairs[pair_key] = index

        include, include_err = _parse_include(raw.get("IncludeAssignment") or "")
        if include is None:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="IncludeAssignment",
                    message=include_err or "",
                )
            )
            continue

        parsed.append(
            ManualAssignmentRow(
                reviewer_id=reviewer.id,
                reviewee_id=reviewee.id,
                reviewer_email=reviewer.email,
                reviewer_name=reviewer.name,
                reviewee_identifier=reviewee.email_or_identifier,
                reviewee_name=reviewee.name,
                include=include,
                pair_context_1=(raw.get("PairContext1") or "").strip() or None,
                pair_context_2=(raw.get("PairContext2") or "").strip() or None,
                pair_context_3=(raw.get("PairContext3") or "").strip() or None,
                assignment_context_1=(raw.get("AssignmentContext1") or "").strip() or None,
                assignment_context_2=(raw.get("AssignmentContext2") or "").strip() or None,
                assignment_context_3=(raw.get("AssignmentContext3") or "").strip() or None,
            )
        )

    return ManualParseResult(rows=parsed, issues=issues)


def manual_rows_to_pairs(
    rows: list[ManualAssignmentRow],
    reviewers: list[Reviewer],
    reviewees: list[Reviewee],
) -> tuple[list[tuple[Reviewer, Reviewee]], list[dict[str, Any] | None], list[bool]]:
    reviewer_by_id = {r.id: r for r in reviewers}
    reviewee_by_id = {r.id: r for r in reviewees}
    pairs: list[tuple[Reviewer, Reviewee]] = []
    contexts: list[dict[str, Any] | None] = []
    includes: list[bool] = []
    for row in rows:
        pairs.append((reviewer_by_id[row.reviewer_id], reviewee_by_id[row.reviewee_id]))
        ctx: dict[str, Any] = {}
        for slot in (1, 2, 3):
            pair_value = getattr(row, f"pair_context_{slot}")
            if pair_value:
                ctx[f"pair_context_{slot}"] = pair_value
            asn_value = getattr(row, f"assignment_context_{slot}")
            if asn_value:
                ctx[f"assignment_context_{slot}"] = asn_value
        contexts.append(ctx or None)
        includes.append(row.include)
    return pairs, contexts, includes


def get_or_create_default_instrument(
    db: Session, review_session: ReviewSession
) -> Instrument:
    """Backwards-compatible wrapper around ``ensure_default_instrument``.

    Kept so existing tests and call sites that import this name still
    work; the canonical helper is now ``app.services.instruments``.
    """
    from app.services.instruments import ensure_default_instrument

    return ensure_default_instrument(db, review_session)


def existing_count(db: Session, session_id: int) -> int:
    stmt = select(Assignment.id).where(Assignment.session_id == session_id)
    return len(db.execute(stmt).all())


def _is_self_review(reviewer: Reviewer, reviewee: Reviewee) -> bool:
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
    """
    reviewers_list = list(reviewers)
    reviewees_list = list(reviewees)
    return sum(
        1
        for r in reviewers_list
        for ree in reviewees_list
        if _is_self_review(r, ree)
    )


def count_self_reviews_in_assignments(
    db: Session, session_id: int
) -> int:
    """Count saved Assignment rows where reviewer.email matches reviewee identifier."""
    rows = db.execute(
        select(Assignment, Reviewer, Reviewee)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        .where(Assignment.session_id == session_id)
    ).all()
    return sum(1 for _, reviewer, reviewee in rows if _is_self_review(reviewer, reviewee))


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
            if exclude_self_review and _is_self_review(reviewer, reviewee):
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


def replace_assignments(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    pairs: list[tuple[Reviewer, Reviewee]],
    mode: AssignmentMode,
    correlation_id: str,
    excluded_counts: dict[str, int] | None = None,
    filename: str | None = None,
    contexts: list[dict[str, Any] | None] | None = None,
    includes: list[bool] | None = None,
) -> tuple[int, int]:
    """Replace all assignments for the session. Returns (replaced, new).

    ``excluded_counts`` is a generic map of exclusion-reason -> row count
    (e.g. ``{"self_review": 3}``). Recorded on the audit event detail.
    Future RuleBased exclusions (tag mismatch, capacity caps, deny lists)
    plug in as additional keys without a schema change.
    """
    if contexts is not None and len(contexts) != len(pairs):
        raise ValueError("contexts length must match pairs length")
    if includes is not None and len(includes) != len(pairs):
        raise ValueError("includes length must match pairs length")

    instrument = get_or_create_default_instrument(db, review_session)

    replaced = existing_count(db, review_session.id)
    db.execute(delete(Assignment).where(Assignment.session_id == review_session.id))

    for index, (reviewer, reviewee) in enumerate(pairs):
        db.add(
            Assignment(
                session_id=review_session.id,
                reviewer_id=reviewer.id,
                reviewee_id=reviewee.id,
                instrument_id=instrument.id,
                include=includes[index] if includes is not None else True,
                context=contexts[index] if contexts is not None else None,
                created_by_mode=mode.value,
            )
        )

    review_session.assignment_mode = mode.value
    db.flush()

    audit.write_event(
        db,
        event_type="assignments.generated",
        summary=(
            f"Generated {len(pairs)} assignments via {mode.value} "
            f"(replaced {replaced})"
        ),
        actor_user_id=user.id,
        session_id=review_session.id,
        detail={
            "mode": mode.value,
            "replaced_count": replaced,
            "new_count": len(pairs),
            "excluded_counts": excluded_counts or {},
            "filename": filename,
        },
        correlation_id=correlation_id,
    )

    db.commit()
    return replaced, len(pairs)


def list_reviewers(db: Session, session_id: int) -> list[Reviewer]:
    return list(
        db.execute(
            select(Reviewer)
            .where(Reviewer.session_id == session_id)
            .order_by(Reviewer.id)
        ).scalars()
    )


def list_reviewees(db: Session, session_id: int) -> list[Reviewee]:
    return list(
        db.execute(
            select(Reviewee)
            .where(Reviewee.session_id == session_id)
            .order_by(Reviewee.id)
        ).scalars()
    )


def list_pairs(
    db: Session, session_id: int, *, limit: int = PAIR_PREVIEW_LIMIT
) -> list[Assignment]:
    """Return saved Assignment rows with reviewer + reviewee eagerly loaded.

    Ordered by (reviewer_id, reviewee_id) to match the FullMatrix preview.
    """
    stmt = (
        select(Assignment)
        .options(joinedload(Assignment.reviewer), joinedload(Assignment.reviewee))
        .where(Assignment.session_id == session_id)
        .order_by(Assignment.reviewer_id, Assignment.reviewee_id)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


def delete_all_assignments(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str,
) -> int:
    """Remove every Assignment for the session. Clears assignment_mode."""
    rows = list(
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    deleted = len(rows)
    for row in rows:
        db.delete(row)
    review_session.assignment_mode = None
    db.flush()

    audit.write_event(
        db,
        event_type="assignments.deleted_all",
        summary=f"Deleted all {deleted} assignments",
        actor_user_id=user.id,
        session_id=review_session.id,
        detail={"deleted_count": deleted},
        correlation_id=correlation_id,
    )
    db.commit()
    return deleted
