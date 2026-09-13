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

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Assignment,
    Instrument,
    ReviewSession,
    SessionRuleSet,
)
from app.services.instruments import _instrument_label


@dataclass(frozen=True)
class InstrumentStatusBlock:
    """One read-only status block per instrument on the Assignments
    page. Renders above the pairs preview table.

    Fields:

    - ``instrument_id`` — int primary key + deep-link anchor.
    - ``instrument_label`` — display label
      (``short_label or name`` — the same friendly label the
      reviewer surface page-buttons use).
    - ``rule_name`` — the pinned RuleSet's name; ``None`` when
      ``Instrument.rule_set_id`` is NULL ("— No rule pinned —").
    - ``eligible_count`` — pairs the engine would produce if run
      now against the current rosters / relationships, read from the
      reconcile diff. Recomputes on every page load, so roster edits
      show before Generate. Unpinned instruments carry a real figure
      too: a NULL ``rule_set_id`` is Full Matrix at the diff site.
    - ``generated_count`` — actual ``Assignment`` rows on this
      instrument right now.
    - ``self_review_total`` — count of self-review rows on this
      instrument (``active + deactivated``). ``0`` when the
      instrument has no self-review pairs in its assignments.
    - ``self_review_active_count`` — self-review rows on this
      instrument with ``include=True``.
    - ``self_review_checkbox_state`` — ``"checked"`` /
      ``"unchecked"`` / ``"indeterminate"``. Drives the per-
      instrument Self review column checkbox; mixed states render
      indeterminate via inline JS.
    - ``self_review_toggle_url`` — POST target for the Self
      review checkbox's bulk-flip form.
    - ``included_count`` — generated rows on this instrument with
      ``include=True``. Drives the **Included** column pill on the
      Assignments page status table; lags ``generated_count`` when
      individual rows (e.g. self-reviews) have been deactivated.
    - ``is_stale`` — the instrument has materialised rows and a
      regenerate would insert or delete at least one pair. Read from
      the engine's reconcile diff, so it cannot disagree with what
      Generate would do. Never-generated instruments read ``False``:
      a run would insert their whole fan-out, and an always-on badge
      is one the operator learns to ignore.
    - ``edit_url`` — deep link to the matching Instrument card.
    """

    instrument_id: int
    instrument_label: str
    is_group: bool
    rule_name: str | None
    eligible_count: int
    generated_count: int
    group_count: int | None
    included_count: int
    self_review_total: int
    self_review_active_count: int
    self_review_checkbox_state: str
    self_review_toggle_url: str
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
    - ``instruments_url`` — deep link to the Instruments page,
      surfaced on the Generate disabled-state nudge.
    """

    status_blocks: list[InstrumentStatusBlock]
    pinned_instrument_count: int
    instruments_url: str


def build_assignments_page_context(
    db: Session, review_session: ReviewSession
) -> AssignmentsPageContext:
    """Build the context for the Assignments page's status-block
    region and Generate affordance. Single page-load engine pass
    via :func:`evaluate_session_rule_eligibility`.
    """
    from app.services import assignments as assignments_service
    from app.services import responses as responses_service

    # Staleness is read from the engine's own diff — one reconcile walk
    # for the session, keyed by instrument id. The retired per-rule
    # eligible count it replaces could not answer the question: equal
    # counts hide a rule change that swaps one pair for another.
    reconcile_state = assignments_service.staleness_by_instrument(
        db, review_session
    )

    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    # Per-instrument group count — distinct (reviewer, group_key)
    # over a group-scoped instrument's generated assignments. Empty
    # for a session with no group-scoped instrument.
    group_instrument_ids = {
        i.id for i in instruments if i.group_kind is not None
    }
    group_count_by_instrument: dict[int, int] = {}
    if group_instrument_ids:
        group_assignments = list(
            db.execute(
                select(Assignment)
                .options(joinedload(Assignment.reviewee))
                .where(
                    Assignment.session_id == review_session.id,
                    Assignment.instrument_id.in_(group_instrument_ids),
                )
            ).scalars()
        )
        group_key_by_assignment = responses_service.group_keys(
            db,
            assignments=group_assignments,
            session_id=review_session.id,
        )
        groups_seen: dict[int, set[tuple[int, tuple[str, ...]]]] = {}
        for assignment in group_assignments:
            groups_seen.setdefault(assignment.instrument_id, set()).add(
                (
                    assignment.reviewer_id,
                    group_key_by_assignment.get(assignment.id, ()),
                )
            )
        group_count_by_instrument = {
            instrument_id: len(groups)
            for instrument_id, groups in groups_seen.items()
        }
    rule_set_rows = {
        row.id: row
        for row in db.execute(
            select(SessionRuleSet).where(
                SessionRuleSet.session_id == review_session.id
            )
        ).scalars()
    }
    generated_by_instrument = assignments_service.existing_count_per_instrument(
        db, review_session.id
    )
    included_by_instrument = assignments_service.included_count_per_instrument(
        db, review_session.id
    )
    self_review_breakdown = (
        assignments_service.self_review_breakdown_per_instrument(
            db, review_session.id
        )
    )

    pinned_count = 0
    blocks: list[InstrumentStatusBlock] = []
    for instrument in instruments:
        rule_id = instrument.rule_set_id
        if rule_id is not None:
            pinned_count += 1
            rule_row = rule_set_rows.get(rule_id)
            rule_name = rule_row.name if rule_row is not None else None
        else:
            rule_name = None
        generated_count = generated_by_instrument.get(instrument.id, 0)
        included_count = included_by_instrument.get(instrument.id, 0)
        state = reconcile_state.get(instrument.id)
        is_stale = state.stale if state is not None else False
        eligible_count = state.eligible if state is not None else 0
        sr_active, sr_deactivated = self_review_breakdown.get(
            instrument.id, (0, 0)
        )
        sr_total = sr_active + sr_deactivated
        if sr_total == 0 or sr_active == sr_total:
            sr_state = "checked"
        elif sr_active == 0:
            sr_state = "unchecked"
        else:
            sr_state = "indeterminate"
        blocks.append(
            InstrumentStatusBlock(
                instrument_id=instrument.id,
                instrument_label=_instrument_label(instrument),
                is_group=instrument.group_kind is not None,
                rule_name=rule_name,
                eligible_count=eligible_count,
                generated_count=generated_count,
                group_count=(
                    group_count_by_instrument.get(instrument.id)
                    if generated_count
                    else None
                ),
                included_count=included_count,
                self_review_total=sr_total,
                self_review_active_count=sr_active,
                self_review_checkbox_state=sr_state,
                self_review_toggle_url=(
                    f"/operator/sessions/{review_session.id}"
                    f"/assignments/{instrument.id}/self-reviews/active"
                ),
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
        instruments_url=(
            f"/operator/sessions/{review_session.id}/instruments"
        ),
    )
