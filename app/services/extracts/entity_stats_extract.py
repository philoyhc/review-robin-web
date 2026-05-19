"""Entity stats extracts — Segment 18H Part 3.

Two analysis-facing per-session CSVs that ship **only inside the
Zip-all bundle**: a Reviewer stats CSV and a Reviewee stats CSV.
Each carries the plain roster shape plus aggregate response-activity
columns.

These are deliberately *not* offered as individual downloads — the
round-trippable Reviewers / Reviewees CSVs keep that role, and
adding stats columns to them would break the importer contract.
The stats files exist purely as an at-a-glance activity summary
alongside the porting bundle.

Every metric is reported as a **draft / submitted pair**: the Draft
column aggregates responses still saved as a draft (``submitted_at``
unset); the Submitted column aggregates submitted responses. Only
responses with a non-empty value count. A group-scoped instrument's
answer is fanned across its member assignments at save time; the
field / char metrics dedupe that fan-out so a group answer counts
once per group on the reviewer side.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Response,
    ResponseTypeDefinition,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services import responses as responses_service

__all__ = [
    "REVIEWER_STATS_HEADER",
    "REVIEWEE_STATS_HEADER",
    "build_entity_stats",
]


# Pinned in a contract test so a rename forces a deliberate update.
REVIEWER_STATS_HEADER: tuple[str, ...] = (
    "ReviewerName",
    "ReviewerEmail",
    "ReviewerTag1",
    "ReviewerTag2",
    "ReviewerTag3",
    "RevieweesReviewedDraft",
    "RevieweesReviewedSubmitted",
    "FieldsAnsweredDraft",
    "FieldsAnsweredSubmitted",
    "RequiredFieldsAnsweredDraft",
    "RequiredFieldsAnsweredSubmitted",
    "StringResponseCharsDraft",
    "StringResponseCharsSubmitted",
)

REVIEWEE_STATS_HEADER: tuple[str, ...] = (
    "RevieweeName",
    "RevieweeEmail",
    "RevieweeTag1",
    "RevieweeTag2",
    "RevieweeTag3",
    "PhotoLink",
    "ReviewersDraft",
    "ReviewersSubmitted",
    "FieldsAnsweredDraft",
    "FieldsAnsweredSubmitted",
    "RequiredFieldsAnsweredDraft",
    "RequiredFieldsAnsweredSubmitted",
    "StringResponseCharsDraft",
    "StringResponseCharsSubmitted",
)


@dataclass
class _Bucket:
    """One draft-or-submitted accumulator for a single entity."""

    partners: set[int] = field(default_factory=set)
    fields_answered: int = 0
    required_fields_answered: int = 0
    string_chars: int = 0


def _new_acc() -> dict[str, _Bucket]:
    return {"draft": _Bucket(), "submitted": _Bucket()}


def build_entity_stats(
    db: Session, review_session: ReviewSession
) -> tuple[list[tuple[str, ...]], list[tuple[str, ...]]]:
    """Return ``(reviewer_rows, reviewee_rows)`` for the bundle.

    Each list is a header row followed by one row per roster entry
    (active rows first, then by name / email — matching the
    Reviewers / Reviewees CSVs). Roster entries with no responses
    still get a row, with zero counts.
    """

    reviewers = list(
        db.execute(
            select(Reviewer)
            .where(Reviewer.session_id == review_session.id)
            .order_by(
                (Reviewer.status != "active").asc(),
                Reviewer.name,
                Reviewer.email,
            )
        ).scalars()
    )
    reviewees = list(
        db.execute(
            select(Reviewee)
            .where(Reviewee.session_id == review_session.id)
            .order_by(
                (Reviewee.status != "active").asc(),
                Reviewee.name,
                Reviewee.email_or_identifier,
            )
        ).scalars()
    )

    reviewer_acc: dict[int, dict[str, _Bucket]] = {
        r.id: _new_acc() for r in reviewers
    }
    reviewee_acc: dict[int, dict[str, _Bucket]] = {
        r.id: _new_acc() for r in reviewees
    }

    # Group key per assignment on a group-scoped instrument; the
    # fan-out copies a group answer onto every member assignment,
    # so on the reviewer side they must collapse to one count.
    assignments = list(
        db.execute(
            select(Assignment).where(
                Assignment.session_id == review_session.id
            )
        ).scalars()
    )
    group_key_by_assignment = responses_service.group_keys(
        db, assignments=assignments, session_id=review_session.id
    )
    seen_reviewer_group: set[
        tuple[int, int, tuple[str, ...], int, str]
    ] = set()

    stmt = (
        select(
            Assignment.reviewer_id,
            Assignment.reviewee_id,
            Assignment.id,
            Assignment.instrument_id,
            InstrumentResponseField.id,
            InstrumentResponseField.required,
            ResponseTypeDefinition.data_type,
            Response.value,
            Response.submitted_at,
        )
        .join(Assignment, Response.assignment_id == Assignment.id)
        .join(Instrument, Assignment.instrument_id == Instrument.id)
        .join(
            InstrumentResponseField,
            Response.response_field_id == InstrumentResponseField.id,
        )
        .join(
            ResponseTypeDefinition,
            InstrumentResponseField.response_type_id
            == ResponseTypeDefinition.id,
        )
        .where(Assignment.session_id == review_session.id)
        .execution_options(yield_per=1000)
    )

    for (
        reviewer_id,
        reviewee_id,
        assignment_id,
        instrument_id,
        field_id,
        required,
        data_type,
        value,
        submitted_at,
    ) in db.execute(stmt):
        if not value:
            # ``None`` (field cleared) or empty string — the reviewer
            # left no content, so it is not a "field with a response".
            continue
        bucket = "submitted" if submitted_at is not None else "draft"
        is_string = data_type == "String"
        char_len = len(value)

        # Reviewee side — each member assignment holds exactly one
        # copy of a group answer, so no fan-out dedupe is needed.
        ree = reviewee_acc[reviewee_id][bucket]
        ree.partners.add(reviewer_id)
        ree.fields_answered += 1
        if required:
            ree.required_fields_answered += 1
        if is_string:
            ree.string_chars += char_len

        # Reviewer side — a group answer is fanned across every
        # member assignment; count each member toward "reviewees
        # reviewed" but the field / char metrics once per group.
        rer = reviewer_acc[reviewer_id][bucket]
        rer.partners.add(reviewee_id)
        group_key = group_key_by_assignment.get(assignment_id)
        if group_key is not None:
            cell = (
                reviewer_id,
                instrument_id,
                group_key,
                field_id,
                bucket,
            )
            if cell in seen_reviewer_group:
                continue
            seen_reviewer_group.add(cell)
        rer.fields_answered += 1
        if required:
            rer.required_fields_answered += 1
        if is_string:
            rer.string_chars += char_len

    reviewer_rows: list[tuple[str, ...]] = [REVIEWER_STATS_HEADER]
    for reviewer in reviewers:
        draft = reviewer_acc[reviewer.id]["draft"]
        submitted = reviewer_acc[reviewer.id]["submitted"]
        reviewer_rows.append(
            (
                reviewer.name,
                reviewer.email,
                reviewer.tag_1 or "",
                reviewer.tag_2 or "",
                reviewer.tag_3 or "",
                str(len(draft.partners)),
                str(len(submitted.partners)),
                str(draft.fields_answered),
                str(submitted.fields_answered),
                str(draft.required_fields_answered),
                str(submitted.required_fields_answered),
                str(draft.string_chars),
                str(submitted.string_chars),
            )
        )

    reviewee_rows: list[tuple[str, ...]] = [REVIEWEE_STATS_HEADER]
    for reviewee in reviewees:
        draft = reviewee_acc[reviewee.id]["draft"]
        submitted = reviewee_acc[reviewee.id]["submitted"]
        reviewee_rows.append(
            (
                reviewee.name,
                reviewee.email_or_identifier,
                reviewee.tag_1 or "",
                reviewee.tag_2 or "",
                reviewee.tag_3 or "",
                reviewee.profile_link or "",
                str(len(draft.partners)),
                str(len(submitted.partners)),
                str(draft.fields_answered),
                str(submitted.fields_answered),
                str(draft.required_fields_answered),
                str(submitted.required_fields_answered),
                str(draft.string_chars),
                str(submitted.string_chars),
            )
        )

    return reviewer_rows, reviewee_rows
