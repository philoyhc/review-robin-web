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


# --------------------------------------------------------------------------- #
# Per-row CRUD — Segment 15F PR 5 stage 2.
#
# The mutator surface the 15F Relationships Setup page lights up.
# ``save_relationships`` stays the bulk CSV wipe-and-replace path;
# these cover single-row authoring + selection-driven status flips.
# --------------------------------------------------------------------------- #


class RelationshipOperationError(ValueError):
    """Raised when a relationship mutation violates an invariant.

    ``code`` is a stable machine identifier the route translates to
    an HTTP status; ``message`` is the human-readable explanation.

    Codes:
    - ``not_in_session`` — a reviewer / reviewee id (or a bulk row
      id) doesn't belong to the target session.
    - ``duplicate_pair`` — the ``(reviewer, reviewee)`` pair already
      has a relationship row (the UNIQUE constraint).
    - ``invalid_status`` — status not in ``{"active", "inactive"}``.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_UNSET: object = object()


def _normalised_rel_status(status: str) -> str:
    value = (status or "active").strip().lower()
    if value not in _VALID_STATUS:
        raise RelationshipOperationError(
            "invalid_status",
            f"Status must be one of {sorted(_VALID_STATUS)}; got {status!r}.",
        )
    return value


def _normalised_rel_tag(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _require_session_member(
    db: Session,
    *,
    session_id: int,
    model: type,
    member_id: int,
    label: str,
) -> object:
    obj = db.execute(
        select(model).where(
            model.id == member_id, model.session_id == session_id
        )
    ).scalar_one_or_none()
    if obj is None:
        raise RelationshipOperationError(
            "not_in_session",
            f"{label} id {member_id} does not belong to this session.",
        )
    return obj


def _pair_taken(
    db: Session,
    *,
    session_id: int,
    reviewer_id: int,
    reviewee_id: int,
    exclude_id: int | None = None,
) -> bool:
    stmt = select(Relationship.id).where(
        Relationship.session_id == session_id,
        Relationship.reviewer_id == reviewer_id,
        Relationship.reviewee_id == reviewee_id,
    )
    if exclude_id is not None:
        stmt = stmt.where(Relationship.id != exclude_id)
    return db.execute(stmt).first() is not None


def create_relationship(
    db: Session,
    *,
    review_session: ReviewSession,
    reviewer_id: int,
    reviewee_id: int,
    tag_1: str | None = None,
    tag_2: str | None = None,
    tag_3: str | None = None,
    status: str = "active",
    user: User,
    correlation_id: str | None = None,
) -> Relationship:
    """Insert a new Relationship row (Segment 15F PR 5 stage 3 — Add
    a new row). Validates that the reviewer and reviewee belong to
    the session and rejects a duplicate ``(reviewer, reviewee)``
    pair against the UNIQUE constraint. Emits ``relationship.created``
    (snapshot envelope); returns the persisted row."""
    _require_session_member(
        db,
        session_id=review_session.id,
        model=Reviewer,
        member_id=reviewer_id,
        label="Reviewer",
    )
    _require_session_member(
        db,
        session_id=review_session.id,
        model=Reviewee,
        member_id=reviewee_id,
        label="Reviewee",
    )
    clean_status = _normalised_rel_status(status)
    clean_tag_1 = _normalised_rel_tag(tag_1)
    clean_tag_2 = _normalised_rel_tag(tag_2)
    clean_tag_3 = _normalised_rel_tag(tag_3)

    if _pair_taken(
        db,
        session_id=review_session.id,
        reviewer_id=reviewer_id,
        reviewee_id=reviewee_id,
    ):
        raise RelationshipOperationError(
            "duplicate_pair",
            "A relationship for this reviewer / reviewee pair "
            "already exists.",
        )

    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason="relationship_created",
        correlation_id=correlation_id,
    )

    relationship = Relationship(
        session_id=review_session.id,
        reviewer_id=reviewer_id,
        reviewee_id=reviewee_id,
        tag_1=clean_tag_1,
        tag_2=clean_tag_2,
        tag_3=clean_tag_3,
        status=clean_status,
    )
    db.add(relationship)
    db.flush()

    audit.write_event(
        db,
        event_type="relationship.created",
        summary=f"Created relationship #{relationship.id}",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.snapshot(
            {
                "relationship_id": relationship.id,
                "reviewer_id": reviewer_id,
                "reviewee_id": reviewee_id,
                "status": clean_status,
                "tag_1": clean_tag_1,
                "tag_2": clean_tag_2,
                "tag_3": clean_tag_3,
            }
        ),
        correlation_id=correlation_id,
    )
    db.commit()
    return relationship


def update_relationship(
    db: Session,
    *,
    relationship: Relationship,
    reviewer_id: int | object = _UNSET,
    reviewee_id: int | object = _UNSET,
    tag_1: str | None | object = _UNSET,
    tag_2: str | None | object = _UNSET,
    tag_3: str | None | object = _UNSET,
    status: str | object = _UNSET,
    user: User,
    correlation_id: str | None = None,
) -> dict[str, list[object]]:
    """Field-level update — reviewer / reviewee included (full-row
    edit). Re-points are validated against the session roster and
    the ``(reviewer, reviewee)`` UNIQUE constraint. Emits
    ``relationship.updated`` only when at least one field changed;
    returns the changes dict."""
    session_id = relationship.session_id
    proposed: dict[str, object] = {}
    if reviewer_id is not _UNSET:
        _require_session_member(
            db,
            session_id=session_id,
            model=Reviewer,
            member_id=reviewer_id,  # type: ignore[arg-type]
            label="Reviewer",
        )
        proposed["reviewer_id"] = reviewer_id
    if reviewee_id is not _UNSET:
        _require_session_member(
            db,
            session_id=session_id,
            model=Reviewee,
            member_id=reviewee_id,  # type: ignore[arg-type]
            label="Reviewee",
        )
        proposed["reviewee_id"] = reviewee_id
    if status is not _UNSET:
        proposed["status"] = _normalised_rel_status(status)  # type: ignore[arg-type]
    if tag_1 is not _UNSET:
        proposed["tag_1"] = _normalised_rel_tag(tag_1)  # type: ignore[arg-type]
    if tag_2 is not _UNSET:
        proposed["tag_2"] = _normalised_rel_tag(tag_2)  # type: ignore[arg-type]
    if tag_3 is not _UNSET:
        proposed["tag_3"] = _normalised_rel_tag(tag_3)  # type: ignore[arg-type]

    final_reviewer = proposed.get("reviewer_id", relationship.reviewer_id)
    final_reviewee = proposed.get("reviewee_id", relationship.reviewee_id)
    if (
        final_reviewer != relationship.reviewer_id
        or final_reviewee != relationship.reviewee_id
    ) and _pair_taken(
        db,
        session_id=session_id,
        reviewer_id=final_reviewer,  # type: ignore[arg-type]
        reviewee_id=final_reviewee,  # type: ignore[arg-type]
        exclude_id=relationship.id,
    ):
        raise RelationshipOperationError(
            "duplicate_pair",
            "A relationship for this reviewer / reviewee pair "
            "already exists.",
        )

    changes: dict[str, list[object]] = {}
    for field, new_value in proposed.items():
        old_value = getattr(relationship, field)
        if old_value != new_value:
            changes[field] = [old_value, new_value]

    if not changes:
        return {}

    lifecycle.invalidate_if_validated(
        db,
        review_session=relationship.session,
        user=user,
        reason="relationship_updated",
        correlation_id=correlation_id,
    )

    # Snapshot the pre-edit pair before ``setattr`` applies a
    # re-point — the old pair's group-scoped responses need
    # defuncting too.
    old_pair = (relationship.reviewer_id, relationship.reviewee_id)

    for field, (_, new_value) in changes.items():
        setattr(relationship, field, new_value)
    db.flush()

    # A relationship edit mis-attributes the answer copies fanned
    # onto group-scoped Response rows two ways: a grouping
    # pair-context tag value changes, or the row is re-pointed to a
    # different pair (its tags move off the old pair and onto the
    # new one). Delete the affected rows so the group re-derives
    # cleanly (Segment 13C PR 5; re-point handling Segment 18H).
    # No-op unless a group instrument is boundaried on pair context.
    from app.services import responses as responses_service

    repointed = "reviewer_id" in changes or "reviewee_id" in changes
    defuncted = (
        responses_service.defunct_group_responses_for_relationship_change(
            db,
            session_id=session_id,
            pairs={
                old_pair,
                (relationship.reviewer_id, relationship.reviewee_id),
            },
            changed_tag_fields={
                f for f in changes if f.startswith("tag_")
            },
            repointed=repointed,
        )
    )

    audit.write_event(
        db,
        event_type="relationship.updated",
        summary=f"Updated relationship #{relationship.id}",
        actor_user_id=user.id,
        session=relationship.session,
        payload=audit.changes(changes),
        refs={"relationship_id": relationship.id},
        context=(
            {"defuncted_group_responses": defuncted} if defuncted else None
        ),
        correlation_id=correlation_id,
    )
    db.commit()
    return changes


def _bulk_set_status(
    db: Session,
    *,
    review_session: ReviewSession,
    relationship_ids: list[int],
    target_status: str,
    event_type: str,
    user: User,
    correlation_id: str | None,
) -> list[int]:
    """Shared implementation for bulk_inactivate / bulk_reactivate."""
    clean_target = _normalised_rel_status(target_status)
    if not relationship_ids:
        return []

    candidates = list(
        db.execute(
            select(Relationship)
            .where(
                Relationship.session_id == review_session.id,
                Relationship.id.in_(relationship_ids),
            )
            .order_by(Relationship.id)
        ).scalars()
    )
    missing = set(relationship_ids) - {r.id for r in candidates}
    if missing:
        raise RelationshipOperationError(
            "not_in_session",
            f"Relationship ids {sorted(missing)} do not belong to "
            f"session {review_session.id}.",
        )

    flipped = [r for r in candidates if r.status != clean_target]
    if not flipped:
        return []

    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason="relationship_bulk_status_change",
        correlation_id=correlation_id,
    )

    flipped_ids = [r.id for r in flipped]
    for r in flipped:
        r.status = clean_target
    db.flush()

    audit.write_event(
        db,
        event_type=event_type,
        summary=(
            f"Flipped {len(flipped_ids)} relationship"
            f"{'' if len(flipped_ids) == 1 else 's'} → {clean_target}"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.snapshot({"relationship_ids": flipped_ids}),
        correlation_id=correlation_id,
    )
    db.commit()
    return flipped_ids


def bulk_inactivate(
    db: Session,
    *,
    review_session: ReviewSession,
    relationship_ids: list[int],
    user: User,
    correlation_id: str | None = None,
) -> list[int]:
    """Flip ``status="inactive"`` on every relationship in
    ``relationship_ids`` not already inactive. Returns the flipped
    ids."""
    return _bulk_set_status(
        db,
        review_session=review_session,
        relationship_ids=relationship_ids,
        target_status="inactive",
        event_type="relationship.bulk_inactivated",
        user=user,
        correlation_id=correlation_id,
    )


def bulk_reactivate(
    db: Session,
    *,
    review_session: ReviewSession,
    relationship_ids: list[int],
    user: User,
    correlation_id: str | None = None,
) -> list[int]:
    """Flip ``status="active"`` on every relationship in
    ``relationship_ids`` not already active. Returns the flipped
    ids."""
    return _bulk_set_status(
        db,
        review_session=review_session,
        relationship_ids=relationship_ids,
        target_status="active",
        event_type="relationship.bulk_reactivated",
        user=user,
        correlation_id=correlation_id,
    )


__all__ = [
    "RelationshipOperationError",
    "bulk_inactivate",
    "bulk_reactivate",
    "create_relationship",
    "delete_all_relationships",
    "existing_count",
    "fields_with_data",
    "list_for_session",
    "pair_context_lookup",
    "parse_relationship_csv",
    "save_relationships",
    "update_relationship",
]
