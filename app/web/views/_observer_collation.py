"""View-shape adapter for the observer collation surface.

Composes the building blocks shipped in earlier slices —
``observer_cohort.materialize_cohort``,
``collation.build_cohort_stats_for_instrument``,
``visibility_policies.resolve_mode`` — into a per-instrument
list of sections the ``/me/sessions/{id}/collation`` template
can iterate over.

Per the MVP shape in ``guide/observers.md``, each section
carries the two cohort-stats rows (reviewer side + reviewee
side) + a conditional download URL whose presence depends on
the instrument's Band 3 observer-audience mode:

- ``raw`` / ``anonymized`` → download URL points at the
  per-instrument CSV route (the consumer of
  ``serialize_by_instrument`` with cohort_filter +
  identification).
- ``summarized`` → ``download_url is None``; the surface
  shows a "summary only" note instead.

A section only appears when the observer-audience policy
``resolve_mode`` returns a non-None mode for the current
session window (matches the visibility-policy gate the
operator authored on Band 3).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentResponseField,
    Observer,
    ReviewSession,
)
from app.services import session_lifecycle as lifecycle
from app.services import visibility_policies
from app.services.collation import (
    CohortStatsRow,
    build_cohort_stats_for_instrument,
)
from app.services.observer_cohort import materialize_cohort

from ._instruments import instrument_heading


@dataclass(frozen=True)
class InstrumentCollationSection:
    """One per visible instrument on the observer surface."""

    instrument_id: int
    title: str
    description: str | None
    fields: list[InstrumentResponseField]
    mode: str
    """``"raw"`` / ``"anonymized"`` / ``"summarized"`` — the
    Band 3 observer-audience mode that resolved for the
    current session window. Drives the row-3 download
    branch."""

    reviewer_stats: CohortStatsRow
    """Row 1 — aggregates over the cohort's reviewers."""

    reviewee_stats: CohortStatsRow
    """Row 2 — aggregates over the cohort's reviewees."""

    download_url: str | None
    """Row 3 — non-None for ``raw`` / ``anonymized`` modes;
    ``None`` for ``summarized`` (no download offered)."""


@dataclass(frozen=True)
class ObserverCollationContext:
    """Template context for the observer collation surface."""

    sections: list[InstrumentCollationSection]
    cohort_empty: bool
    """True when the observer's cohort_rule didn't materialize
    any reviewer or reviewee ids (no saved rule, or the rule
    matched zero rows). The template shows the empty-cohort
    message instead of the section list."""


def build_observer_collation_context(
    db: Session,
    *,
    observer: Observer,
    review_session: ReviewSession,
) -> ObserverCollationContext:
    """Compose the per-instrument list the collation surface
    renders, scoped to the observer's cohort and the Band 3
    visibility policies."""
    cohort = materialize_cohort(db, observer=observer)
    if not cohort.reviewer_ids and not cohort.reviewee_ids:
        return ObserverCollationContext(sections=[], cohort_empty=True)

    while_ongoing_open = lifecycle.is_ready(review_session)
    after_release_open = lifecycle.is_response_release_window_open(
        review_session
    )

    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    total = len(instruments)

    sections: list[InstrumentCollationSection] = []
    for position, instrument in enumerate(instruments):
        policies = visibility_policies.list_for_instrument(
            db, instrument.id
        )
        policy = policies.get("observer")
        mode = visibility_policies.resolve_mode(
            policy,
            while_ongoing_open=while_ongoing_open,
            after_release_open=after_release_open,
        )
        if mode is None:
            continue

        reviewer_stats, reviewee_stats = (
            build_cohort_stats_for_instrument(
                db, instrument=instrument, cohort=cohort
            )
        )

        download_url: str | None = (
            None
            if mode == "summarized"
            else (
                f"/me/sessions/{review_session.id}/collation/"
                f"instruments/{instrument.id}.csv"
            )
        )

        heading = instrument_heading(
            instrument=instrument,
            position=position,
            total_count=total,
        )

        sections.append(
            InstrumentCollationSection(
                instrument_id=instrument.id,
                title=heading.title,
                description=heading.subtitle,
                fields=list(instrument.response_fields),
                mode=mode,
                reviewer_stats=reviewer_stats,
                reviewee_stats=reviewee_stats,
                download_url=download_url,
            )
        )

    return ObserverCollationContext(
        sections=sections,
        cohort_empty=False,
    )
