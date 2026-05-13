"""Assignments page view-shape (Segment 15B Slice 3a).

Owns the per-instrument **status blocks** + **Generate** affordance
context for ``/operator/sessions/{id}/assignments``. Pre-15B the
page rendered a Rule Based card (pick a rule + Generate); Slice 3a
flips it to preview-only with rule selection living on the
Instrument cards (Slice 2a). The materialise action stays on this
page as the page-level Generate button.

Read alongside:

- :mod:`app.web.views._instruments` — owns the per-card rule
  picker context (Slice 2a).
- :mod:`app.services.assignments` — owns the materialiser
  (``replace_assignments``) and the per-instrument count +
  last-generated audit-event helpers.
- :mod:`app.services.rules.session_library
  .evaluate_session_rule_eligibility` — the engine pass shared
  with the Instruments page picker.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession, SessionRuleSet


@dataclass(frozen=True)
class InstrumentStatusBlock:
    """One read-only status block per instrument on the Assignments
    page. Renders above the pairs preview table.

    Fields:

    - ``instrument_id`` / ``instrument_name`` — display + deep-link.
    - ``rule_name`` — the pinned RuleSet's name; ``None`` when
      ``Instrument.rule_set_id`` is NULL ("— No rule pinned —").
    - ``eligible_count`` — pairs the engine would produce if run
      now against the current rosters / relationships. ``0`` when
      no rule is pinned. Recomputes on every page load — reflects
      roster edits immediately, before Generate.
    - ``generated_count`` — actual ``Assignment`` rows on this
      instrument right now.
    - ``last_generated_at`` — timestamp of the most recent
      ``assignments.generated`` audit event scoped to this
      instrument; ``None`` when no per-instrument event exists
      (instrument never generated, or only pre-Slice-1 aggregated
      events that lack ``refs.instrument_id``).
    - ``is_stale`` — ``eligible_count != generated_count`` AND a
      rule is pinned. Operator hasn't clicked Generate since the
      rule / roster last changed.
    - ``edit_url`` — deep link to the matching Instrument card.
    """

    instrument_id: int
    instrument_name: str
    rule_name: str | None
    eligible_count: int
    generated_count: int
    last_generated_at: datetime | None
    is_stale: bool
    edit_url: str


@dataclass(frozen=True)
class AssignmentsPageContext:
    """Page-level context for the Slice 3a Assignments page.

    Fields:

    - ``status_blocks`` — one per instrument in this session, in
      ``Instrument.order`` then ``id`` order.
    - ``pinned_instrument_count`` — how many instruments have a
      non-NULL ``rule_set_id``. Drives the disabled state on the
      page-level Generate button (zero pinned ⇒ disabled with
      "Pin rules on the Instruments page first" nudge).
    - ``any_stale`` — ``True`` when any pinned instrument's
      eligible / generated counts diverge. Drives the
      "Pairs may be stale" badge near the Generate button.
    - ``instruments_url`` — deep link to the Instruments page,
      surfaced on the Generate disabled-state nudge.
    """

    status_blocks: list[InstrumentStatusBlock]
    pinned_instrument_count: int
    any_stale: bool
    instruments_url: str


def build_assignments_page_context(
    db: Session, review_session: ReviewSession
) -> AssignmentsPageContext:
    """Build the context for the Assignments page's status-block
    region and Generate affordance. Single page-load engine pass
    via :func:`evaluate_session_rule_eligibility`.
    """
    from app.services import assignments as assignments_service
    from app.services.rules import session_library

    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    rule_set_rows = {
        row.id: row
        for row in db.execute(
            select(SessionRuleSet).where(
                SessionRuleSet.session_id == review_session.id
            )
        ).scalars()
    }
    eligibility_by_rule = session_library.evaluate_session_rule_eligibility(
        db, review_session
    )
    generated_by_instrument = assignments_service.existing_count_per_instrument(
        db, review_session.id
    )
    latest_event_by_instrument = (
        assignments_service.latest_generated_event_per_instrument(
            db, review_session.id
        )
    )

    pinned_count = 0
    any_stale = False
    blocks: list[InstrumentStatusBlock] = []
    for instrument in instruments:
        rule_id = instrument.rule_set_id
        if rule_id is not None:
            pinned_count += 1
            rule_row = rule_set_rows.get(rule_id)
            rule_name = rule_row.name if rule_row is not None else None
            eligible_count = eligibility_by_rule.get(rule_id, 0)
        else:
            rule_name = None
            eligible_count = 0
        generated_count = generated_by_instrument.get(instrument.id, 0)
        last_event = latest_event_by_instrument.get(instrument.id)
        last_generated_at = last_event.created_at if last_event else None
        is_stale = (
            rule_id is not None
            and eligible_count != generated_count
        )
        if is_stale:
            any_stale = True
        blocks.append(
            InstrumentStatusBlock(
                instrument_id=instrument.id,
                instrument_name=instrument.name,
                rule_name=rule_name,
                eligible_count=eligible_count,
                generated_count=generated_count,
                last_generated_at=last_generated_at,
                is_stale=is_stale,
                edit_url=(
                    f"/operator/sessions/{review_session.id}/instruments"
                    f"#instrument-{instrument.id}"
                ),
            )
        )
    return AssignmentsPageContext(
        status_blocks=blocks,
        pinned_instrument_count=pinned_count,
        any_stale=any_stale,
        instruments_url=(
            f"/operator/sessions/{review_session.id}/instruments"
        ),
    )
