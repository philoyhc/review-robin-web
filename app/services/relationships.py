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

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.schemas.imports import (
    RelationshipImportRow,
    RevieweeImportRow,
    ReviewerImportRow,
)
from app.schemas.validation import Severity, ValidationIssue
from app.services import audit, field_labels, session_lifecycle as lifecycle
from app.services import unit_of_work
from app.services.csv_imports import (
    AppendConflict,
    ParseResult,
    _cell,
    _missing_columns_issues,
    _none_if_blank,
    _read_dict_rows,
    cell_length_issues,
    comma_tag_message,
    decode_csv,
    over_long_field_message,
    tag_comma_issues,
)
from app.services.email_identity import normalize_email
from app.services.roster_bulk import (
    bulk_delete,
    bulk_set_status,
    clear_redrawn_groups,
    pair_context_groups_before,
)
from app.services.roster_status import ROSTER_STATUSES, normalise_status


def parse_relationship_csv(
    content: bytes,
    *,
    reviewers: Sequence[Reviewer | IncomingReviewer],
    reviewees: Sequence[Reviewee | IncomingReviewee],
    reviewers_uploaded: bool = False,
    reviewees_uploaded: bool = False,
    reviewees_mirrored: bool = False,
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

    ``reviewers_uploaded`` / ``reviewees_uploaded`` say the matching
    list stands for a roster file uploaded alongside this one
    (:func:`rosters_for_relationships`), so an unknown email names that
    file instead of the roster. Its rows then carry stand-in ids: such
    a parse checks, and the save must parse again once the rosters are
    written. ``reviewees_mirrored`` says the reviewees stand for the
    uploaded Reviewers file under symmetric review (segment 20B), so an
    unknown reviewee names that file.
    """

    source = "relationships"
    issues: list[ValidationIssue] = []

    text, decode_issue = decode_csv(content, source)
    if decode_issue is not None:
        return ParseResult(rows=[], issues=[decode_issue])
    assert text is not None

    raw_rows, fieldnames, captured_labels, count_issue = _read_dict_rows(
        text, source
    )
    if count_issue is not None:
        return ParseResult(rows=[], issues=[count_issue])
    assert raw_rows is not None

    issues.extend(
        _missing_columns_issues(
            fieldnames, ["ReviewerEmail", "RevieweeEmail"], source
        )
    )
    if issues:
        return ParseResult(rows=[], issues=issues)

    reviewer_by_email = {normalize_email(r.email): r for r in reviewers}
    reviewee_by_identifier = {
        normalize_email(r.email_or_identifier): r for r in reviewees
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
                    problem="ReviewerEmail is blank",
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
                    problem="RevieweeEmail is blank",
                )
            )
            continue

        reviewer = reviewer_by_email.get(normalize_email(reviewer_email))
        if reviewer is None:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="ReviewerEmail",
                    message=(
                        f"Unknown reviewer '{reviewer_email}' — not in "
                        f"the uploaded Reviewers file."
                        if reviewers_uploaded
                        else f"Unknown reviewer '{reviewer_email}' — "
                        f"import reviewers first."
                    ),
                    problem=(
                        "ReviewerEmail is not in the uploaded Reviewers file"
                        if reviewers_uploaded
                        else "ReviewerEmail is not on the Reviewers roster "
                        "(import reviewers first)"
                    ),
                )
            )
            continue
        reviewee = reviewee_by_identifier.get(normalize_email(reviewee_email))
        if reviewee is None:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="RevieweeEmail",
                    message=(
                        f"Unknown reviewee '{reviewee_email}' — not in "
                        f"the uploaded Reviewers file (symmetric review)."
                        if reviewees_mirrored
                        else f"Unknown reviewee '{reviewee_email}' — not in "
                        f"the uploaded Reviewees file."
                        if reviewees_uploaded
                        else f"Unknown reviewee '{reviewee_email}' — "
                        f"import reviewees first."
                    ),
                    problem=(
                        "RevieweeEmail is not in the uploaded Reviewers file "
                        "(symmetric review)"
                        if reviewees_mirrored
                        else "RevieweeEmail is not in the uploaded Reviewees file"
                        if reviewees_uploaded
                        else "RevieweeEmail is not on the Reviewees roster "
                        "(import reviewees first)"
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
                    problem="A reviewer–reviewee pair appears on more than one row",
                )
            )
            continue

        # not-identity: a roster Status enum from a CSV cell, not an email.
        # Blank or absent column ⇒ ``active``: ``_cell`` returns "" for
        # both, so the ``or`` is the whole default.
        status_raw = (_cell(raw, "Status") or "active").strip().lower()
        if status_raw not in ROSTER_STATUSES:
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
                    problem="Status is not active or inactive",
                )
            )
            continue

        # 19S Item 4 row 9 — reserve the pair only now, on a row that has
        # passed every check, so ``seen_pairs`` holds exactly the pairs in
        # ``parsed`` and ``prior_index`` always names a row the caller can
        # see in ``ParseResult.rows``. Reserving it at the duplicate test
        # above let a row rejected further down consume its own key, and a
        # later valid row for the same pair was then told it duplicated a
        # row that never parsed. **No import lost a pair either way** —
        # every error is blocking and all three callers refuse the whole
        # file — so the defect was the misleading message, not data.
        row = RelationshipImportRow(
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            tag_1=_none_if_blank(raw, "PairContextTag1"),
            tag_2=_none_if_blank(raw, "PairContextTag2"),
            tag_3=_none_if_blank(raw, "PairContextTag3"),
            status=status_raw,
            status_given=bool(_cell(raw, "Status")),
        )
        length_issues = cell_length_issues(
            row,
            Relationship,
            {
                "tag_1": "PairContextTag1",
                "tag_2": "PairContextTag2",
                "tag_3": "PairContextTag3",
            },
            source=source,
            row_number=index,
        )
        length_issues += tag_comma_issues(
            row,
            {
                "tag_1": "PairContextTag1",
                "tag_2": "PairContextTag2",
                "tag_3": "PairContextTag3",
            },
            source=source,
            row_number=index,
        )
        if length_issues:
            issues.extend(length_issues)
            continue
        seen_pairs[(reviewer.id, reviewee.id)] = index
        parsed.append(row)

    return ParseResult(
        rows=parsed, issues=issues, field_labels=captured_labels, columns=frozenset(fieldnames)
    )


@dataclass(frozen=True)
class IncomingReviewer:
    """A reviewer row from a file uploaded alongside a Relationships
    file: what :func:`parse_relationship_csv` reads of a ``Reviewer``.
    ``id`` is a stand-in (negative, so never a real row's)."""

    id: int
    email: str


@dataclass(frozen=True)
class IncomingReviewee:
    """As :class:`IncomingReviewer`, for a reviewee row."""

    id: int
    email_or_identifier: str


def rosters_for_relationships(
    db: Session,
    session_id: int,
    *,
    incoming_reviewers: Sequence[ReviewerImportRow] | None = None,
    incoming_reviewees: Sequence[RevieweeImportRow] | None = None,
) -> tuple[list[Reviewer | IncomingReviewer], list[Reviewee | IncomingReviewee]]:
    """The reviewers and reviewees a Relationships file is checked
    against: an uploaded roster file's rows where one is attached,
    otherwise the session's current roster (``guide/quick_setup_update.md``
    Item 1). Pass the result to :func:`parse_relationship_csv` with
    ``reviewers_uploaded`` / ``reviewees_uploaded`` set to match.

    Every row counts, active or not, as the current rosters do here.
    """
    from app.services.assignments import list_reviewees, list_reviewers

    reviewers: list[Reviewer | IncomingReviewer] = (
        [
            IncomingReviewer(id=-index, email=row.email)
            for index, row in enumerate(incoming_reviewers, start=1)
        ]
        if incoming_reviewers is not None
        else list(list_reviewers(db, session_id))
    )
    reviewees: list[Reviewee | IncomingReviewee] = (
        [
            IncomingReviewee(
                id=-index, email_or_identifier=row.email_or_identifier
            )
            for index, row in enumerate(incoming_reviewees, start=1)
        ]
        if incoming_reviewees is not None
        else list(list_reviewees(db, session_id))
    )
    return reviewers, reviewees


def parse_relationship_upload(
    db: Session,
    session_id: int,
    content: bytes,
    *,
    incoming_reviewers: Sequence[ReviewerImportRow] | None = None,
    incoming_reviewees: Sequence[RevieweeImportRow] | None = None,
    symmetric: bool = False,
) -> ParseResult:
    """Check a Relationships file uploaded beside roster files, before
    any of them saves: against each uploaded roster, else the session's
    (:func:`rosters_for_relationships`).

    Under symmetric review (segment 20B) the uploaded reviewers are also
    the reviewees, so with a Reviewers file and no Reviewees file the
    file is checked against the reviewers' addresses rather than the
    roster they will replace (Codex on #3490)."""
    reviewers, reviewees = rosters_for_relationships(
        db,
        session_id,
        incoming_reviewers=incoming_reviewers,
        incoming_reviewees=incoming_reviewees,
    )
    mirrored = (
        symmetric and incoming_reviewers is not None and incoming_reviewees is None
    )
    if mirrored:
        reviewees = [
            IncomingReviewee(id=-index, email_or_identifier=row.email)
            for index, row in enumerate(incoming_reviewers, start=1)
        ]
    return parse_relationship_csv(
        content,
        reviewers=reviewers,
        reviewees=reviewees,
        reviewers_uploaded=incoming_reviewers is not None,
        reviewees_uploaded=incoming_reviewees is not None,
        reviewees_mirrored=mirrored,
    )


def existing_count(db: Session, session_id: int) -> int:
    stmt = select(func.count(Relationship.id)).where(
        Relationship.session_id == session_id
    )
    return int(db.execute(stmt).scalar_one())


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


def relationship_append_conflicts(
    db: Session, *, session_id: int, rows: Sequence[RelationshipImportRow]
) -> list[ValidationIssue]:
    """The rows an append to the relationships refuses (segment 19Z;
    author, 2026-10-31): a pair already a relationship, compared on the
    resolved ``(reviewer_id, reviewee_id)`` as the within-file rule is.
    Rows are numbered as the parser numbers them, from 1."""
    held = set(
        db.execute(
            select(Relationship.reviewer_id, Relationship.reviewee_id).where(
                Relationship.session_id == session_id
            )
        ).tuples()
    )
    return [
        ValidationIssue(
            severity=Severity.error,
            source="relationships",
            row_number=index,
            field="ReviewerEmail",
            message="This reviewer and reviewee are already a relationship.",
            problem="The pair is already a relationship",
        )
        for index, row in enumerate(rows, start=1)
        if (row.reviewer_id, row.reviewee_id) in held
    ]


def save_relationships(
    db: Session,
    *,
    session: ReviewSession,
    user: User,
    rows: list[RelationshipImportRow],
    filename: str,
    correlation_id: str,
    field_labels_captured: dict[tuple[str, str], str] | None = None,
    acknowledged_loss: int | None = None,
    append: bool = False,
    merge: bool = False,
    columns: frozenset[str] = frozenset(),
) -> tuple[int, int]:
    """Wipe-and-replace the session's relationships table from the
    parsed rows. Returns ``(replaced, new)``.

    Mirrors ``save_reviewers`` / ``save_reviewees`` in shape:
    invalidates the lifecycle if the session was validated,
    deletes existing rows, inserts the new ones, emits the
    ``relationships.imported`` audit event, reconciles the header's
    friendly labels, and commits once (``unit_of_work.atomic``).

    With ``append`` (segment 19Z) the existing pairs stay and the rows
    are added; a pair already a relationship refuses the whole file
    (`AppendConflict`), checked under the session lock before anything
    is written. The header's labels are upserted and none cleared.

    With ``merge`` (the upsert amendment) a pair already a relationship
    takes the row's non-blank tags, and its Status when the file has the
    column, writing ``relationship.updated``; any other pair is added.
    The group-clear ask covers a tag change as it covers a new pair.
    """
    # One commit for the replace, its display fields and its labels, so
    # the label reconcile's gate can't refuse after a committed replace
    # (findings Bc4; Codex on #2882).
    with unit_of_work.atomic(db):
        lifecycle.require_editable(db, session)
        if append:
            conflicts = relationship_append_conflicts(
                db, session_id=session.id, rows=rows
            )
            if conflicts:
                raise AppendConflict(conflicts)
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
        before = pair_context_groups_before(db, session_id=session.id)
        if append or merge:
            replaced, kept = 0, len(existing_rows)
        else:
            replaced, kept = len(existing_rows), 0
            for row in existing_rows:
                db.delete(row)
            db.flush()

        added, updated, unchanged = 0, 0, 0
        held_pairs = {(r.reviewer_id, r.reviewee_id): r for r in existing_rows} if merge else {}
        for row in rows:
            held = held_pairs.get((row.reviewer_id, row.reviewee_id))
            if held is None:
                db.add(_relationship_to_orm(row, session.id))
                added += 1
                continue
            changes: dict[str, list[object]] = {}
            for name in ("tag_1", "tag_2", "tag_3", "status"):
                value = getattr(row, name)
                if value is None or (name == "status" and not row.status_given):
                    continue
                if getattr(held, name) != value:
                    changes[name] = [getattr(held, name), value]
            if not changes:
                unchanged += 1
                continue
            for name, (_, value) in changes.items():
                setattr(held, name, value)
            audit.write_event(
                db,
                event_type="relationship.updated",
                summary=f"Updated relationship #{held.id} (merge)",
                actor_user_id=user.id,
                session=session,
                payload=audit.changes(changes),
                refs={"relationship_id": held.id},
                correlation_id=correlation_id,
            )
            updated += 1
        db.flush()
        context = {"filename": filename} if filename else {}
        if append:
            context["mode"] = "append"
        if merge:
            context["mode"] = "upsert"
        context.update(
            clear_redrawn_groups(
                db,
                session_id=session.id,
                before=before,
                acknowledged_loss=acknowledged_loss,
            )
            or {}
        )
        _recompute_self_review(db, session_id=session.id)

        audit.write_event(
            db,
            event_type="relationships.imported",
            summary=(
                f"Merged relationships: {added} added, {updated} updated"
                if merge
                else f"Appended {len(rows)} relationships (kept {kept})"
                if append
                else f"Imported {len(rows)} relationships (replaced {replaced})"
            ),
            actor_user_id=user.id,
            session=session,
            payload=audit.counts(
                **(
                    {"new": added, "updated": updated, "unchanged": unchanged}
                    if merge
                    else {"new": len(rows), "kept": kept}
                    if append
                    else {"new": len(rows), "replaced": replaced}
                )
            ),
            context=context or None,
            correlation_id=correlation_id,
        )

        # Lazy-seed pair_context display fields for any populated tag
        # slots — see guide/unfinished_business item #14. Pre-15D this
        # fired off the manual-CSV save path through Assignment.context;
        # post-PR-6b the data lives on the relationships table itself,
        # so the seeding hook moves to the relationships save.
        from app.services.instruments import seed_display_fields_from_assignments

        seed_display_fields_from_assignments(db, session)
        # Segment 19C Item 1 — reconcile pair-context friendly labels from
        # the relationships header (upsert present, clear absent).
        if field_labels_captured is not None:
            field_labels.apply_import(
                db,
                session,
                source_type="pair_context",
                captured=field_labels_captured,
                user=user,
                correlation_id=correlation_id,
                clear_absent=not (append or merge),
            )
    return replaced, (added if merge else len(rows))


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


def _recompute_self_review(db: Session, *, session_id: int) -> None:
    """Re-derive ``Assignment.is_self_review`` after a relationship
    change (findings B33). A group instrument boundaried on pair
    context reads its group keys off the active relationship rows, so
    adding, removing, retagging or (in)activating one can move a
    reviewer into or out of a group."""
    from app.services.assignments import (
        recompute_self_review_classification,
    )

    recompute_self_review_classification(db, session_id=session_id)


def delete_all_relationships(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str,
    acknowledged_loss: int | None = None,
) -> int:
    """Wipe every relationships row for the session. Returns the
    deleted row count. Mirrors ``csv_imports.delete_all_reviewers``
    in shape: invalidates a validated session before the wipe,
    emits ``relationships.deleted_all``, commits."""

    lifecycle.require_editable(db, review_session)
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
    before = pair_context_groups_before(db, session_id=review_session.id)
    deleted = len(existing_rows)
    for row in existing_rows:
        db.delete(row)
    db.flush()
    context = clear_redrawn_groups(
        db,
        session_id=review_session.id,
        before=before,
        acknowledged_loss=acknowledged_loss,
    )
    _recompute_self_review(db, session_id=review_session.id)

    audit.write_event(
        db,
        event_type="relationships.deleted_all",
        summary=f"Deleted {deleted} relationships",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(deleted=deleted),
        context=context,
        correlation_id=correlation_id,
    )

    db.commit()
    return deleted


def delete_all_group_loss(db: Session, *, session_id: int) -> int:
    """The saved responses ``delete_all_relationships`` would clear on
    pair-context groups, counted without deleting anything, so the
    Danger Zone's tick can name them up front as the other rosters'
    do (segment 19X Item 3). The delete runs inside a savepoint that is
    rolled back. 0 when no pair-context group instrument has an answer."""
    from app.services import responses as responses_service

    before = pair_context_groups_before(db, session_id=session_id)
    if not before:
        return 0
    savepoint = db.begin_nested()
    try:
        for row in db.execute(
            select(Relationship).where(Relationship.session_id == session_id)
        ).scalars():
            db.delete(row)
        db.flush()
        try:
            # An acknowledged count of 0 refuses any loss, with the count.
            clear_redrawn_groups(
                db, session_id=session_id, before=before, acknowledged_loss=0
            )
        except responses_service.GroupAnswersWouldClear as exc:
            return exc.count
        return 0
    finally:
        savepoint.rollback()


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
    - ``too_long`` — a value is longer than its column.
    - ``comma_in_tag`` — a tag value contains a comma (findings Gc1).
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_UNSET: object = object()

# Each column's name in a ``too_long`` or ``comma_in_tag`` message. A
# tag is named by its slot, not by the session's friendly label for it.
_FIELD_LABELS = {"tag_1": "Tag 1", "tag_2": "Tag 2", "tag_3": "Tag 3"}


def _refuse_over_long(values: dict[str, object]) -> None:
    message = over_long_field_message(Relationship, values, _FIELD_LABELS)
    if message is not None:
        raise RelationshipOperationError("too_long", message)
    message = comma_tag_message(values, _FIELD_LABELS)
    if message is not None:
        raise RelationshipOperationError("comma_in_tag", message)


def _normalised_rel_status(status: str) -> str:
    return normalise_status(status, error_cls=RelationshipOperationError)


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
    acknowledged_loss: int | None = None,
) -> Relationship:
    """Insert a new Relationship row (Segment 15F PR 5 stage 3 — Add
    a new row). Validates that the reviewer and reviewee belong to
    the session and rejects a duplicate ``(reviewer, reviewee)``
    pair against the UNIQUE constraint. Emits ``relationship.created``
    (snapshot envelope); returns the persisted row."""
    lifecycle.require_editable(db, review_session)
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
    _refuse_over_long(
        {"tag_1": clean_tag_1, "tag_2": clean_tag_2, "tag_3": clean_tag_3}
    )

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

    before = pair_context_groups_before(db, session_id=review_session.id)
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
    context = clear_redrawn_groups(
        db,
        session_id=review_session.id,
        before=before,
        acknowledged_loss=acknowledged_loss,
    )
    _recompute_self_review(db, session_id=review_session.id)

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
        context=context,
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
    acknowledged_loss: int | None = None,
) -> dict[str, list[object]]:
    """Field-level update — reviewer / reviewee included (full-row
    edit). Re-points are validated against the session roster and
    the ``(reviewer, reviewee)`` UNIQUE constraint. Emits
    ``relationship.updated`` only when at least one field changed;
    returns the changes dict."""
    lifecycle.require_editable(db, relationship.session)
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
    _refuse_over_long(proposed)

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

    # A relationship edit can move its pair, or the pair it is
    # re-pointed off, to another pair-context group: a grouping tag
    # value changes, the row is re-pointed (its tags leave the old pair
    # for the new one), or its status flips (an inactive relationship
    # reads as empty tags). The group a pair joins gained a member and
    # is cleared; the one it left only shrank and keeps its answer
    # (author's rulings 2026-10-17; findings B34 for status).
    before = pair_context_groups_before(db, session_id=session_id)

    for field, (_, new_value) in changes.items():
        setattr(relationship, field, new_value)
    db.flush()

    context = clear_redrawn_groups(
        db,
        session_id=session_id,
        before=before,
        acknowledged_loss=acknowledged_loss,
    )
    _recompute_self_review(db, session_id=session_id)

    audit.write_event(
        db,
        event_type="relationship.updated",
        summary=f"Updated relationship #{relationship.id}",
        actor_user_id=user.id,
        session=relationship.session,
        payload=audit.changes(changes),
        refs={"relationship_id": relationship.id},
        context=context,
        correlation_id=correlation_id,
    )
    db.commit()
    return changes


def bulk_inactivate(
    db: Session,
    *,
    review_session: ReviewSession,
    relationship_ids: list[int],
    user: User,
    correlation_id: str | None = None,
    acknowledged_loss: int | None = None,
) -> list[int]:
    """Flip ``status="inactive"`` on every relationship in
    ``relationship_ids`` not already inactive. Returns the flipped
    ids."""
    lifecycle.require_editable(db, review_session)
    return bulk_set_status(
        db,
        review_session=review_session,
        model=Relationship,
        ids=relationship_ids,
        target_status="inactive",
        normalise_status=_normalised_rel_status,
        error_cls=RelationshipOperationError,
        event_type="relationship.bulk_inactivated",
        entity_noun="relationship",
        user=user,
        correlation_id=correlation_id,
        acknowledged_loss=acknowledged_loss,
    )


def bulk_reactivate(
    db: Session,
    *,
    review_session: ReviewSession,
    relationship_ids: list[int],
    user: User,
    correlation_id: str | None = None,
    acknowledged_loss: int | None = None,
) -> list[int]:
    """Flip ``status="active"`` on every relationship in
    ``relationship_ids`` not already active. Returns the flipped
    ids."""
    lifecycle.require_editable(db, review_session)
    return bulk_set_status(
        db,
        review_session=review_session,
        model=Relationship,
        ids=relationship_ids,
        target_status="active",
        normalise_status=_normalised_rel_status,
        error_cls=RelationshipOperationError,
        event_type="relationship.bulk_reactivated",
        entity_noun="relationship",
        user=user,
        correlation_id=correlation_id,
        acknowledged_loss=acknowledged_loss,
    )


__all__ = [
    "RelationshipOperationError",
    "bulk_inactivate",
    "bulk_reactivate",
    "create_relationship",
    "delete_all_relationships",
    "existing_count",
    "list_for_session",
    "pair_context_lookup",
    "parse_relationship_csv",
    "relationship_append_conflicts",
    "save_relationships",
    "update_relationship",
]


def delete_selected(
    db: Session,
    *,
    review_session: ReviewSession,
    relationship_ids: list[int],
    user: User,
    correlation_id: str | None = None,
    acknowledged_loss: int | None = None,
) -> tuple[int, int, int]:
    """Delete the selected relationships. Returns
    ``(deleted, cascaded_assignments, cascaded_responses)``.

    The selection-driven sibling of :func:`bulk_inactivate` — same
    id list, same session scoping, same ``not_in_session`` refusal —
    and of ``delete_all_relationships``, whose cascade semantics it
    inherits rather than reinvents. Segment 19I Item 2.
    """
    lifecycle.require_editable(db, review_session)
    return bulk_delete(
        db,
        review_session=review_session,
        model=Relationship,
        ids=relationship_ids,
        error_cls=RelationshipOperationError,
        event_type="relationship.bulk_deleted",
        entity_noun="relationship",
        user=user,
        correlation_id=correlation_id,
        acknowledged_loss=acknowledged_loss,
    )
