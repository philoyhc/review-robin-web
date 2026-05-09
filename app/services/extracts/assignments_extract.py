"""Manual assignments extract — Segment 12A-1 PR 3.

Streams the session's assignment rows as a CSV whose column shape
matches the existing manual-assignments importer
(``app.services.assignments.parse_manual_csv``). Only emitted on
sessions whose ``assignment_mode == "manual"`` — rule-based and
full-matrix sessions are derived from operator typing elsewhere
(a RuleSet selection or a one-click action on the destination),
so re-emitting the rows would freeze a derivation against the
source roster. Per Scenario A's "snapshot the inputs, never the
outputs" rule.

Plan: ``guide/segment_12A-1_export.md`` PR 3.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services.instruments import _instrument_label

__all__ = ["HEADER", "ManualOnlyError", "serialize_assignments"]


# Header tuple matching the importer's required + optional columns
# (assignments.parse_manual_csv:194-203 + IncludeAssignment in the
# row body). The ``Instrument`` column is forward-compatible with
# the multi-instrument upload arriving in Segment 13 — today's
# importer ignores it.
HEADER: tuple[str, ...] = (
    "ReviewerEmail",
    "RevieweeEmail",
    "IncludeAssignment",
    "Instrument",
)


class ManualOnlyError(Exception):
    """Raised by :func:`serialize_assignments` when the session's
    ``assignment_mode`` isn't ``"manual"``. The route catches this
    and returns 404; the Extract Data card surfaces the row as
    disabled with an explanatory note."""

    def __init__(self, mode: str | None) -> None:
        super().__init__(
            f"Assignments extract is manual-only; "
            f"session is in {mode!r} mode"
        )
        self.mode = mode


def serialize_assignments(
    db: Session, review_session: ReviewSession
) -> Iterable[tuple[str, ...]]:
    """Yield CSV rows for ``review_session``'s assignments.

    Raises :class:`ManualOnlyError` when ``assignment_mode`` is
    anything other than ``"manual"`` (rule-based / full-matrix
    sessions don't export — derivations re-derive on the
    destination via the same generation path).

    First yield is :data:`HEADER`; subsequent yields are one tuple
    per ``(assignment, instrument)`` tuple. For multi-instrument
    sessions, the same ``(ReviewerEmail, RevieweeEmail)`` pair
    emits N rows — the upload-side ``parse_manual_csv`` collapses
    repeated pairs into one assignment per instrument-id.

    Order: ``(reviewer.email, reviewee.email_or_identifier,
    instrument.order, instrument.id)`` — deterministic so re-export
    is byte-stable, and grouped by reviewer for human readability.
    """

    if (review_session.assignment_mode or "") != "manual":
        raise ManualOnlyError(review_session.assignment_mode)

    yield HEADER

    instrument_label_by_id: dict[int, str] = {
        instr.id: _instrument_label(instr)
        for instr in db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id
            )
        )
        .scalars()
        .all()
    }

    rows = (
        db.execute(
            select(Assignment, Reviewer, Reviewee, Instrument)
            .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
            .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
            .join(Instrument, Assignment.instrument_id == Instrument.id)
            .where(Assignment.session_id == review_session.id)
            .order_by(
                Reviewer.email,
                Reviewee.email_or_identifier,
                Instrument.order,
                Instrument.id,
            )
        )
        .all()
    )
    for assignment, reviewer, reviewee, instrument in rows:
        yield (
            reviewer.email,
            reviewee.email_or_identifier,
            "true" if assignment.include else "false",
            instrument_label_by_id.get(instrument.id, instrument.name),
        )
