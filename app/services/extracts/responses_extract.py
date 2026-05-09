"""Responses extract — Segment 12A-1 PR 4.

Streams the session's reviewer responses as a wide CSV designed
for **downstream analysis** (Excel pivots, pandas groupby, BI
tools). Different use case from the porting-flow CSVs (settings
+ reviewers + reviewees + assignments): each row is
self-contained — denormalised reviewer / reviewee identity +
tags, instrument + field context, and the response-type name —
so the file is readable without joining against the other
extracts.

No import counterpart. Operators don't upload responses; only
reviewers create them via the response surface.

Plan: ``guide/segment_12A-1_export.md`` "Responses extract"
section + PR 4.
"""

from __future__ import annotations

from collections.abc import Iterable

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

__all__ = ["HEADER", "serialize_responses"]


# 19-column header. Pinned in unit tests so a rename here fails
# loud and forces analysts of the file to update their pipelines
# deliberately.
HEADER: tuple[str, ...] = (
    # Reviewer identity + tags (5 cols).
    "ReviewerName",
    "ReviewerEmail",
    "ReviewerTag1",
    "ReviewerTag2",
    "ReviewerTag3",
    # Reviewee identity + tags (5 cols). Note ``RevieweeEmail``
    # mirrors the rosters CSV header even though the underlying
    # column is ``Reviewee.email_or_identifier``.
    "RevieweeName",
    "RevieweeEmail",
    "RevieweeTag1",
    "RevieweeTag2",
    "RevieweeTag3",
    # Instrument context (2 cols).
    "InstrumentName",
    "InstrumentShortLabel",
    # Field context (3 cols).
    "FieldKey",
    "FieldLabel",
    "ResponseType",
    # Value (1 col). Empty cell ⇒ reviewer cleared the field.
    "Value",
    # Lifecycle (3 cols). ``SubmittedAt`` empty ⇒
    # saved-but-not-submitted draft.
    "SavedAt",
    "SubmittedAt",
    "Version",
)


def serialize_responses(
    db: Session, review_session: ReviewSession
) -> Iterable[tuple[str, ...]]:
    """Yield CSV rows for ``review_session``'s responses.

    First yield is :data:`HEADER`; subsequent yields are one
    tuple per ``Response`` row in deterministic order
    (``(reviewer.email, reviewee.email_or_identifier,
    instrument.order, instrument.id, response_field.order,
    response_field.id)``). Streams through a ``yield_per`` cursor
    so memory stays flat on sessions with hundreds of thousands
    of rows.

    Per the segment plan's "Empty / missing values" section,
    a ``Response`` row with ``value IS NULL`` (reviewer cleared
    the field) emits an empty ``Value`` cell — the row is still
    emitted because the reviewer interacted with the field. A
    field with no ``Response`` row at all (the reviewer never
    touched it) emits no row in the CSV; the row count equals
    ``responses.session_response_count(...)``.
    """

    yield HEADER

    stmt = (
        select(
            Response,
            Reviewer,
            Reviewee,
            Instrument,
            InstrumentResponseField,
            ResponseTypeDefinition,
        )
        .join(Assignment, Response.assignment_id == Assignment.id)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
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
        .order_by(
            Reviewer.email,
            Reviewee.email_or_identifier,
            Instrument.order,
            Instrument.id,
            InstrumentResponseField.order,
            InstrumentResponseField.id,
        )
        .execution_options(yield_per=1000)
    )

    for response, reviewer, reviewee, instrument, field, rtd in db.execute(
        stmt
    ):
        yield (
            reviewer.name,
            reviewer.email,
            reviewer.tag_1 or "",
            reviewer.tag_2 or "",
            reviewer.tag_3 or "",
            reviewee.name,
            reviewee.email_or_identifier,
            reviewee.tag_1 or "",
            reviewee.tag_2 or "",
            reviewee.tag_3 or "",
            instrument.name,
            instrument.short_label or "",
            field.field_key,
            field.label,
            rtd.response_type,
            response.value if response.value is not None else "",
            response.saved_at.isoformat() if response.saved_at else "",
            (
                response.submitted_at.isoformat()
                if response.submitted_at
                else ""
            ),
            str(response.version),
        )
