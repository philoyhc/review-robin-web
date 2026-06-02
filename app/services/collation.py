"""Per-instrument response aggregation for the observer
collation surface.

Given a materialised ``CohortIds`` (from
``app.services.observer_cohort.materialize_cohort``) and an
``Instrument``, computes two aggregate rows per the MVP shape
in ``guide/observers.md``:

- **Row 1 — Reviewer stats.** Aggregates the submitted
  response values where ``Assignment.reviewer_id`` ∈ the
  cohort's reviewers. Answers: *what did the reviewers in my
  cohort write?*
- **Row 2 — Reviewee stats.** Aggregates where
  ``Assignment.reviewee_id`` ∈ the cohort's reviewees.
  Answers: *what did reviewers (anyone) write about the
  reviewees in my cohort?*

Both rows reuse the W16 ``summarize_field`` primitive
(``app.web.views._reviewee_results``) so the per-data-type
aggregation shape (mean / median / min / max for numerical;
per-choice frequencies for List; total + average length for
String) stays consistent with the reviewee ``/results``
surface.

The route + view-shape adapter that compose these stats into
the ``/me/sessions/{id}/collation`` template come in a follow-up
PR; this module is the pure data builder.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Response,
)
from app.services.observer_cohort import CohortIds

# Cross-layer import: ``summarize_field`` is currently defined
# on the reviewee-results view module because that's where its
# first caller landed. The aggregation math is pure (no view
# state); a future PR may relocate it to a service module so the
# services → views import direction inverts.
from app.web.views._reviewee_results import (
    SummarizedFieldCell,
    summarize_field,
)


@dataclass(frozen=True)
class CohortStatsRow:
    """Aggregate stats for one side (reviewer or reviewee) of
    one instrument, scoped to the observer's cohort."""

    response_count: int
    """Number of non-empty submitted response cells that fed the
    aggregates — summed across every response field on the
    instrument. ``0`` ⇒ no responses contributed and every
    ``field_cells`` entry is in its empty state."""

    field_cells: list[SummarizedFieldCell]
    """One per response field on the instrument, in field-order.
    Cell shape varies by ``field.data_type`` — see
    ``SummarizedFieldCell`` for the per-type fields."""


def _ordered_response_fields(
    instrument: Instrument,
) -> list[InstrumentResponseField]:
    """Pin the per-instrument response field order so the
    reviewer-stats and reviewee-stats rows line up column-by-
    column. SQLAlchemy already orders ``Instrument.response_fields``
    by ``order, id``; this helper is a thin facade so the
    surface code reads naturally."""
    return list(instrument.response_fields)


def _gather_stats(
    db: Session,
    *,
    instrument_id: int,
    fields: list[InstrumentResponseField],
    side: str,
    side_ids: frozenset[int],
) -> CohortStatsRow:
    """Aggregate submitted response values for one cohort side.

    ``side`` is ``"reviewer"`` or ``"reviewee"`` and selects
    which ``Assignment`` column to filter on. ``side_ids`` is
    the cohort's frozenset for that side; an empty set returns
    an all-empty ``CohortStatsRow`` shaped to the instrument's
    fields without touching the database.
    """
    if not fields:
        return CohortStatsRow(response_count=0, field_cells=[])
    if not side_ids:
        return CohortStatsRow(
            response_count=0,
            field_cells=[
                SummarizedFieldCell(data_type=f.data_type) for f in fields
            ],
        )

    side_column: Any
    if side == "reviewer":
        side_column = Assignment.reviewer_id
    elif side == "reviewee":
        side_column = Assignment.reviewee_id
    else:
        raise ValueError(f"unknown cohort side {side!r}")

    rows = db.execute(
        select(Response.response_field_id, Response.value)
        .join(Assignment, Response.assignment_id == Assignment.id)
        .where(
            Assignment.instrument_id == instrument_id,
            side_column.in_(side_ids),
            Response.submitted_at.is_not(None),
        )
    ).all()

    by_field: dict[int, list[str]] = {f.id: [] for f in fields}
    for field_id, value in rows:
        if field_id not in by_field:
            continue
        if value is None:
            continue
        stripped = str(value).strip()
        if not stripped:
            continue
        by_field[field_id].append(stripped)

    response_count = sum(len(v) for v in by_field.values())
    field_cells = [summarize_field(f, by_field[f.id]) for f in fields]
    return CohortStatsRow(
        response_count=response_count, field_cells=field_cells
    )


def build_cohort_stats_for_instrument(
    db: Session,
    *,
    instrument: Instrument,
    cohort: CohortIds,
) -> tuple[CohortStatsRow, CohortStatsRow]:
    """Return ``(reviewer_side_stats, reviewee_side_stats)`` for
    one instrument, scoped to ``cohort``.

    Empty-side handling: when the cohort has no ids on a side,
    that side's row carries ``response_count=0`` + one empty
    ``SummarizedFieldCell`` per response field — the surface
    template can render the "no responses" shape uniformly
    without a separate branch.

    Only submitted responses (``Response.submitted_at IS NOT
    NULL``) contribute. In-progress drafts don't appear in the
    aggregates.
    """
    fields = _ordered_response_fields(instrument)
    reviewer_side = _gather_stats(
        db,
        instrument_id=instrument.id,
        fields=fields,
        side="reviewer",
        side_ids=cohort.reviewer_ids,
    )
    reviewee_side = _gather_stats(
        db,
        instrument_id=instrument.id,
        fields=fields,
        side="reviewee",
        side_ids=cohort.reviewee_ids,
    )
    return reviewer_side, reviewee_side
