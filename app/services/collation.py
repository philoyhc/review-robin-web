"""Per-instrument response aggregation for the observer collation
surface.

Given a materialised ``CohortAssignments`` (from
``app.services.observer_cohort.materialize_cohort_assignments``)
and an ``Instrument``, computes two aggregate rows per the MVP
shape in ``guide/observers.md``:

The cohort rule picks out a pool of in-cohort assignments. Both
rows draw from the **same pool**:

- **Row 1 — Reviewer side.** Headcount badge: distinct reviewers
  in the pool. Aggregate: the same response values as Row 2.
  Answers: *which reviewers are visible to me, and how did they
  respond?*
- **Row 2 — Reviewee side.** Headcount badge: distinct reviewees
  in the pool. Same aggregate as Row 1. Answers: *which reviewees
  are visible to me, and what responses did they receive?*

Because each response cell is tied to exactly one assignment, the
two rows share an identical aggregate; the legitimate
side-asymmetry is the headcount (a tall-narrow pool has few
distinct reviewers + many reviewees, etc.). The W16
``summarize_field`` primitive
(``app.web.views._reviewee_results``) computes the per-data-type
aggregate so the shape stays consistent with the reviewee
``/results`` surface.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentResponseField,
    Response,
)
from app.services.observer_cohort import CohortAssignments

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
    """Aggregate stats for one side (reviewer or reviewee) of one
    instrument, scoped to the observer's cohort pool.

    Both rows in a per-instrument pair share an identical
    ``field_cells`` aggregate + ``response_count`` (one response
    per in-cohort assignment, summarised once). They differ only
    in ``distinct_count`` — the per-side headcount badge.
    """

    distinct_count: int
    """Number of distinct individuals on this side (reviewers for
    Row 1, reviewees for Row 2) present in the in-cohort pool."""

    response_count: int
    """Number of non-empty submitted response cells in the
    in-cohort pool — summed across every response field on the
    instrument. Same on both rows."""

    field_cells: list[SummarizedFieldCell]
    """One per response field, in field-order. Same on both
    rows."""


def _ordered_response_fields(
    instrument: Instrument,
) -> list[InstrumentResponseField]:
    """Pin the per-instrument response field order. SQLAlchemy
    already orders ``Instrument.response_fields`` by ``order, id``;
    this helper is a thin facade so the surface code reads
    naturally."""
    return list(instrument.response_fields)


def build_cohort_stats_for_instrument(
    db: Session,
    *,
    instrument: Instrument,
    cohort: CohortAssignments,
) -> tuple[CohortStatsRow, CohortStatsRow]:
    """Return ``(reviewer_side_row, reviewee_side_row)`` for one
    instrument, scoped to ``cohort.assignment_ids``.

    Both rows share the same ``field_cells`` + ``response_count``
    aggregate (one response per assignment in the pool, summarised
    once). They differ only in ``distinct_count``:
    ``cohort.distinct_reviewer_count`` on Row 1,
    ``cohort.distinct_reviewee_count`` on Row 2.

    Empty pool: returns the per-side distinct counts (typically 0)
    over an all-empty field-cells shape so the surface template
    renders uniformly.

    Only submitted responses (``Response.submitted_at IS NOT
    NULL``) contribute. In-progress drafts don't appear in the
    aggregates.
    """
    fields = _ordered_response_fields(instrument)
    empty_cells = [
        SummarizedFieldCell(data_type=f.data_type) for f in fields
    ]

    if not fields or not cohort.assignment_ids:
        return (
            CohortStatsRow(
                distinct_count=cohort.distinct_reviewer_count,
                response_count=0,
                field_cells=empty_cells,
            ),
            CohortStatsRow(
                distinct_count=cohort.distinct_reviewee_count,
                response_count=0,
                field_cells=empty_cells,
            ),
        )

    rows = db.execute(
        select(Response.response_field_id, Response.value).where(
            Response.assignment_id.in_(cohort.assignment_ids),
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

    return (
        CohortStatsRow(
            distinct_count=cohort.distinct_reviewer_count,
            response_count=response_count,
            field_cells=field_cells,
        ),
        CohortStatsRow(
            distinct_count=cohort.distinct_reviewee_count,
            response_count=response_count,
            field_cells=field_cells,
        ),
    )
