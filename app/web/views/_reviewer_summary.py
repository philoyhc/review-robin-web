"""Reviewer per-session participation-summary view shape.

Segment 17B Phase 2 PR B. Translates the reviewer's responses on
one session into a list of per-instrument sections the
``reviewer/summary.html`` template renders. Read-only — no edit
affordances, no save / submit forms.

The summary page lives alongside the response surface; once a
reviewer has submitted every assigned row on a session the
submit-flow redirect lands them here instead of back on the
surface. The page also stays reachable later (from PR A's
dashboard, the Session column links here when Reviewer Status
is ``submitted``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services import responses as responses_service


@dataclass(frozen=True)
class SummaryFieldCol:
    """One column in a per-instrument summary table."""

    field_key: str
    label: str


@dataclass(frozen=True)
class SummaryRow:
    """One reviewee row in a per-instrument summary table.

    ``values`` is positionally aligned with the section's
    ``field_cols`` — empty string for fields the reviewer left
    blank (or that the field didn't apply to that reviewee).
    Group-scoped instruments collapse member assignments to one
    row carrying the composed group identity in
    :attr:`reviewee_name`.
    """

    reviewee_name: str
    values: list[str]


@dataclass(frozen=True)
class SummarySection:
    """One per-instrument section on the summary page.

    ``position`` is the 1-based positional index the surface route
    uses (``Instrument.order, Instrument.id`` ordered) so the
    section heading matches the reviewer's surface navigation.
    """

    instrument_name: str
    instrument_short_label: str | None
    position: int
    field_cols: list[SummaryFieldCol]
    rows: list[SummaryRow]


@dataclass(frozen=True)
class ReviewerSummaryContext:
    """The full context the ``reviewer/summary.html`` template
    consumes."""

    session: ReviewSession
    sections: list[SummarySection]
    last_submitted_at: datetime | None


def build_reviewer_summary_context(
    db: Session,
    *,
    review_session: ReviewSession,
    reviewer: Reviewer,
) -> ReviewerSummaryContext:
    """Build the read-only summary context for one reviewer.

    Walks the session's instruments in positional order; for each
    one the reviewer has at least one ``Response`` on, emits a
    section with the field columns and one row per reviewee (or
    one row per group on a group-scoped instrument). Instruments
    the reviewer wasn't assigned to are omitted from the section
    list. ``last_submitted_at`` is the most recent ``submitted_at``
    across the reviewer's responses on the session — the page's
    "Submitted on ..." caption.
    """
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )

    # Fan-out / group identity index for group-scoped instruments.
    assignments = list(
        db.execute(
            select(Assignment).where(
                Assignment.session_id == review_session.id,
                Assignment.reviewer_id == reviewer.id,
                Assignment.include.is_(True),
            )
        ).scalars()
    )
    group_key_by_assignment = responses_service.group_keys(
        db, assignments=assignments, session_id=review_session.id
    )
    # ``group_identity`` matches the export helper's composition: the
    # boundary tag values joined by ", " (with the operator's per-
    # instrument RevieweeName-Included setting deferred — group
    # rows on the summary page show the tag identity).
    group_identity: dict[tuple[int, tuple[str, ...]], str] = {}
    for assignment in assignments:
        group_key = group_key_by_assignment.get(assignment.id)
        if group_key is None:
            continue
        identity_key = (assignment.instrument_id, group_key)
        if identity_key not in group_identity:
            tag_part = ", ".join(v for v in group_key if v)
            group_identity[identity_key] = tag_part or "(group)"

    # Pull all of the reviewer's responses + denormalised reviewee /
    # field / instrument context in one query.
    rows = list(
        db.execute(
            select(
                Response,
                Reviewee,
                Instrument,
                InstrumentResponseField,
            )
            .join(Assignment, Response.assignment_id == Assignment.id)
            .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
            .join(Instrument, Assignment.instrument_id == Instrument.id)
            .join(
                InstrumentResponseField,
                Response.response_field_id == InstrumentResponseField.id,
            )
            .where(Assignment.session_id == review_session.id)
            .where(Assignment.reviewer_id == reviewer.id)
        ).all()
    )

    # Index responses by (instrument_id, reviewee_row_key, field_id).
    # For group-scoped instruments, reviewee_row_key is the
    # composed group identity; for per-reviewee instruments it's
    # the reviewee.id.
    cells: dict[tuple[int, str | int, int], str] = {}
    row_order: dict[int, list[str | int]] = {}
    row_label: dict[tuple[int, str | int], str] = {}
    for response, reviewee, instrument, field in rows:
        group_key = group_key_by_assignment.get(response.assignment_id)
        if group_key is not None:
            identity = group_identity.get(
                (instrument.id, group_key), "(group)"
            )
            key: str | int = identity
            label = identity
        else:
            key = reviewee.id
            label = reviewee.name
        cell_key = (instrument.id, key, field.id)
        # Group-scoped fan-out: the same (reviewer, instrument,
        # group, field) cell appears once per member; the first
        # one wins (they all carry the same value by the
        # fan-out invariant).
        if cell_key in cells:
            continue
        cells[cell_key] = (
            response.value if response.value is not None else ""
        )
        order_list = row_order.setdefault(instrument.id, [])
        if key not in order_list:
            order_list.append(key)
        row_label[(instrument.id, key)] = label

    last_submitted_at: datetime | None = None
    for response, _, _, _ in rows:
        if response.submitted_at is None:
            continue
        if last_submitted_at is None or response.submitted_at > last_submitted_at:
            last_submitted_at = response.submitted_at

    sections: list[SummarySection] = []
    for position, instrument in enumerate(instruments, start=1):
        if instrument.id not in row_order:
            continue
        fields = sorted(
            instrument.response_fields, key=lambda f: (f.order, f.id)
        )
        field_cols = [
            SummaryFieldCol(field_key=f.field_key, label=f.label)
            for f in fields
        ]
        # Stable display order: reviewee name (or composed group
        # identity), then natural insertion order as a tiebreak.
        ordered_keys = sorted(
            row_order[instrument.id],
            key=lambda k: row_label[(instrument.id, k)].lower(),
        )
        section_rows: list[SummaryRow] = []
        for key in ordered_keys:
            values = [
                cells.get((instrument.id, key, f.id), "")
                for f in fields
            ]
            section_rows.append(
                SummaryRow(
                    reviewee_name=row_label[(instrument.id, key)],
                    values=values,
                )
            )
        sections.append(
            SummarySection(
                instrument_name=instrument.name,
                instrument_short_label=instrument.short_label,
                position=position,
                field_cols=field_cols,
                rows=section_rows,
            )
        )

    return ReviewerSummaryContext(
        session=review_session,
        sections=sections,
        last_submitted_at=last_submitted_at,
    )


__all__ = [
    "ReviewerSummaryContext",
    "SummaryFieldCol",
    "SummaryRow",
    "SummarySection",
    "build_reviewer_summary_context",
]
