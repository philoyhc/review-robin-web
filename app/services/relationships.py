"""Per-pair attributes service — Segment 15D PR 1.

Owns the ``relationships`` table created inert in 13E PR 2. The
table backs the post-15D Relationships Setup page (15D PR 2) and
the rule-engine ``pair_context.tag_N`` source class (15D PR 3 + 4).
This PR ships the service-layer foundation: a per-entity CSV
importer that mirrors ``parse_reviewer_csv`` /
``parse_reviewee_csv`` and a small CRUD surface the downstream
PRs (and 12A-3 PR 2's Manage page + extract route) consume.

The importer resolves ``ReviewerEmail`` against the session's
existing ``reviewers.email`` and ``RevieweeEmail`` against the
session's existing ``reviewees.email_or_identifier``. Rows that
reference unknown identifiers are rejected. Wipe-and-replace on
save — all existing rows for the session drop before the new ones
land. Audit event ``relationships.imported`` (registered in
``EVENT_SCHEMAS``) carries ``counts.new`` + ``counts.replaced`` +
``context.filename``.
"""

from __future__ import annotations

import csv
import io

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.schemas.imports import RelationshipImportRow
from app.schemas.validation import Severity, ValidationIssue
from app.services import audit, session_lifecycle as lifecycle
from app.services.csv_imports import (
    ParseResult,
    _cell,
    _missing_columns_issues,
    _none_if_blank,
    _read_dict_rows,
    decode_csv,
)

_VALID_STATUS = {"active", "inactive"}


def parse_relationship_csv(
    content: bytes,
    *,
    reviewers: list[Reviewer],
    reviewees: list[Reviewee],
) -> ParseResult:
    """Parse a Relationships CSV against the session's existing rosters.

    Required columns: ``ReviewerEmail``, ``RevieweeEmail``.
    Optional columns: ``PairContextTag1``, ``PairContextTag2``,
    ``PairContextTag3``, ``Status``.

    The status column accepts ``active`` (default when blank) or
    ``inactive``; anything else is a validation error.

    The parser resolves each row's ``ReviewerEmail`` /
    ``RevieweeEmail`` against the session's existing rosters via
    case-insensitive match. Unknown identifiers are validation
    errors. The returned ``RelationshipImportRow`` rows carry the
    resolved FK ids so the save step doesn't repeat the lookup.
    """

    source = "relationships"
    issues: list[ValidationIssue] = []

    text, decode_issue = decode_csv(content, source)
    if decode_issue is not None:
        return ParseResult(rows=[], issues=[decode_issue])
    assert text is not None

    raw_rows, count_issue = _read_dict_rows(text, source)
    if count_issue is not None:
        return ParseResult(rows=[], issues=[count_issue])
    assert raw_rows is not None

    reader = csv.DictReader(io.StringIO(text))
    fieldnames = list(reader.fieldnames or [])
    issues.extend(
        _missing_columns_issues(
            fieldnames, ["ReviewerEmail", "RevieweeEmail"], source
        )
    )
    if issues:
        return ParseResult(rows=[], issues=issues)

    reviewer_by_email = {r.email.casefold(): r for r in reviewers}
    reviewee_by_identifier = {
        r.email_or_identifier.casefold(): r for r in reviewees
    }

    parsed: list[RelationshipImportRow] = []
    seen_pairs: dict[tuple[int, int], int] = {}

    for index, raw in enumerate(raw_rows, start=1):
        reviewer_email = _cell(raw, "ReviewerEmail")
        reviewee_email = _cell(raw, "RevieweeEmail")
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
        if not reviewee_email:
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
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="ReviewerEmail",
                    message=(
                        f"Unknown reviewer '{reviewer_email}' — import "
                        f"reviewers first."
                    ),
                )
            )
            continue
        reviewee = reviewee_by_identifier.get(reviewee_email.casefold())
        if reviewee is None:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="RevieweeEmail",
                    message=(
                        f"Unknown reviewee '{reviewee_email}' — import "
                        f"reviewees first."
                    ),
                )
            )
            continue

        prior_index = seen_pairs.get((reviewer.id, reviewee.id))
        if prior_index is not None:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="ReviewerEmail",
                    message=(
                        f"Duplicate pair ({reviewer_email}, "
                        f"{reviewee_email}) — also on row {prior_index}"
                    ),
                )
            )
            continue
        seen_pairs[(reviewer.id, reviewee.id)] = index

        status_raw = (_cell(raw, "Status") or "active").strip().lower()
        if status_raw == "":
            status_raw = "active"
        if status_raw not in _VALID_STATUS:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="Status",
                    message=(
                        f"Status must be 'active' or 'inactive' "
                        f"(got '{status_raw}')"
                    ),
                )
            )
            continue

        parsed.append(
            RelationshipImportRow(
                reviewer_id=reviewer.id,
                reviewee_id=reviewee.id,
                tag_1=_none_if_blank(raw, "PairContextTag1"),
                tag_2=_none_if_blank(raw, "PairContextTag2"),
                tag_3=_none_if_blank(raw, "PairContextTag3"),
                status=status_raw,
            )
        )

    return ParseResult(rows=parsed, issues=issues)


def existing_count(db: Session, session_id: int) -> int:
    stmt = select(Relationship.id).where(Relationship.session_id == session_id)
    return len(db.execute(stmt).all())


def fields_with_data(db: Session, session_id: int) -> list[str]:
    """CSV column names of relationship fields that hold at least one value.

    Mirrors ``assignments.reviewer_fields_with_data`` /
    ``reviewee_fields_with_data`` in shape: ``ReviewerEmail`` and
    ``RevieweeEmail`` always render when any rows exist (they're
    required); each ``PairContextTag{N}`` is included only if a
    non-empty value lives in that slot; ``Status`` is included when
    any row is ``inactive``.
    """

    labels: list[str] = []
    has_any = (
        db.execute(
            select(Relationship.id)
            .where(Relationship.session_id == session_id)
            .limit(1)
        ).first()
        is not None
    )
    if not has_any:
        return labels
    labels.extend(["ReviewerEmail", "RevieweeEmail"])
    for slot in (1, 2, 3):
        col = getattr(Relationship, f"tag_{slot}")
        found = db.execute(
            select(Relationship.id)
            .where(Relationship.session_id == session_id)
            .where(col.is_not(None))
            .where(col != "")
            .limit(1)
        ).first()
        if found is not None:
            labels.append(f"PairContextTag{slot}")
    inactive_found = db.execute(
        select(Relationship.id)
        .where(Relationship.session_id == session_id)
        .where(Relationship.status == "inactive")
        .limit(1)
    ).first()
    if inactive_found is not None:
        labels.append("Status")
    return labels


def list_for_session(
    db: Session, session_id: int
) -> list[Relationship]:
    """Deterministic ordering for preview / round-trip stability."""

    return list(
        db.execute(
            select(Relationship)
            .where(Relationship.session_id == session_id)
            .order_by(Relationship.reviewer_id, Relationship.reviewee_id)
        ).scalars()
    )


def pair_context_lookup(
    db: Session, session_id: int
) -> dict[tuple[int, int], Relationship]:
    """Eager-loaded ``(reviewer_id, reviewee_id) -> Relationship`` map
    for the rule engine's ``pair_context.tag_N`` resolver
    (15D PR 4)."""

    return {
        (row.reviewer_id, row.reviewee_id): row
        for row in list_for_session(db, session_id)
    }


def save_relationships(
    db: Session,
    *,
    session: ReviewSession,
    user: User,
    rows: list[RelationshipImportRow],
    filename: str,
    correlation_id: str,
) -> tuple[int, int]:
    """Wipe-and-replace the session's relationships table from the
    parsed rows. Returns ``(replaced, new)``.

    Mirrors ``save_reviewers`` / ``save_reviewees`` in shape:
    invalidates the lifecycle if the session was validated,
    deletes existing rows, inserts the new ones, emits the
    ``relationships.imported`` audit event, commits.
    """

    lifecycle.invalidate_if_validated(
        db,
        review_session=session,
        user=user,
        reason="relationships_imported",
        correlation_id=correlation_id,
    )

    existing_rows = list(
        db.execute(
            select(Relationship).where(Relationship.session_id == session.id)
        ).scalars()
    )
    replaced = len(existing_rows)
    for row in existing_rows:
        db.delete(row)
    db.flush()

    for row in rows:
        db.add(_relationship_to_orm(row, session.id))
    db.flush()

    audit.write_event(
        db,
        event_type="relationships.imported",
        summary=f"Imported {len(rows)} relationships (replaced {replaced})",
        actor_user_id=user.id,
        session=session,
        payload=audit.counts(new=len(rows), replaced=replaced),
        context={"filename": filename} if filename else None,
        correlation_id=correlation_id,
    )

    db.commit()

    # Lazy-seed pair_context display fields for any populated tag
    # slots — see guide/unfinished_business item #14. Pre-15D this
    # fired off the manual-CSV save path through Assignment.context;
    # post-PR-6b the data lives on the relationships table itself,
    # so the seeding hook moves to the relationships save.
    from app.services.instruments import seed_display_fields_from_assignments

    if seed_display_fields_from_assignments(db, session):
        db.commit()
    return replaced, len(rows)


def _relationship_to_orm(
    row: RelationshipImportRow, session_id: int
) -> Relationship:
    return Relationship(
        session_id=session_id,
        reviewer_id=row.reviewer_id,
        reviewee_id=row.reviewee_id,
        tag_1=row.tag_1,
        tag_2=row.tag_2,
        tag_3=row.tag_3,
        status=row.status,
    )


def delete_all_relationships(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str,
) -> int:
    """Wipe every relationships row for the session. Returns the
    deleted row count. Mirrors ``csv_imports.delete_all_reviewers``
    in shape: invalidates a validated session before the wipe,
    emits ``relationships.deleted_all``, commits."""

    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason="relationships_deleted_all",
        correlation_id=correlation_id,
    )

    existing_rows = list(
        db.execute(
            select(Relationship).where(
                Relationship.session_id == review_session.id
            )
        ).scalars()
    )
    deleted = len(existing_rows)
    for row in existing_rows:
        db.delete(row)
    db.flush()

    audit.write_event(
        db,
        event_type="relationships.deleted_all",
        summary=f"Deleted {deleted} relationships",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(deleted=deleted),
        correlation_id=correlation_id,
    )

    db.commit()
    return deleted


__all__ = [
    "delete_all_relationships",
    "existing_count",
    "fields_with_data",
    "list_for_session",
    "pair_context_lookup",
    "parse_relationship_csv",
    "save_relationships",
]
