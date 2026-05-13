"""Instruments page view-shapes — operator's per-session
``/operator/sessions/{id}/instruments`` page plus the reviewer-
surface heading + page-button helpers and the per-field render
hints (placeholder / constraint summary).

Slice 6 of the §12.B ladder (``guide/archive/major_refactor.md``).

Owns the ``InstrumentHeading`` / ``PageButton`` dataclasses, the
``page_button_label`` / ``instrument_heading`` builders that drive
the reviewer-surface composition table per
``spec/reviewer-surface.md``, the per-field render hints
(``placeholder_for_field`` / ``constraint_summary_for_field``),
and the operator-page context builder ``build_instruments_context``
that runs the per-request idempotent backfills + state-machine
derivation.

Source range in pre-PR-6 ``_legacy.py``: lines 38-335.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentResponseField,
    ReviewSession,
    User,
)
from app.services import instruments as instruments_service
from app.services import session_lifecycle as lifecycle
from app.web import breadcrumbs

from ._setup import session_status_pills


# Sentinel value the rule-picker `<select>` posts when the operator
# chose the "— No rule —" option. Anything else is an int that
# resolves to a ``session_rule_sets.id``. Lives at module scope so
# both the template (via the form's hidden input default) and the
# route handler agree on the literal.
RULE_PICKER_NO_RULE_VALUE = ""


@dataclass(frozen=True)
class InstrumentHeading:
    """Title + optional subtitle for the per-instrument heading card.

    Title lands on the H2; subtitle on a `.muted` body-weight `<p>`
    below it inside `.card.rs-instrument-card`, which sits in column 1
    of the per-instrument intro grid (`.rs-intro-grid`). Either or
    both can be ``None`` — the template only renders the heading card
    when ``title`` is truthy.

    Composition rules per `spec/reviewer-surface.md` "Above the table
    — heading + help block":

    | total_count | short_label | description | title | subtitle |
    |---|---|---|---|---|
    | >1 | set     | set       | "Page #{N}: {short_label}" | description |
    | >1 | set     | unset     | "Page #{N}: {short_label}" | None |
    | >1 | unset   | set       | "Page #{N}"                | description |
    | >1 | unset   | unset     | "Page #{N}"                | None |
    | 1  | set     | set       | "{short_label}"            | description |
    | 1  | set     | unset     | "{short_label}"            | None |
    | 1  | unset   | set       | "{description}" *          | None *     |
    | 1  | unset   | unset     | None                       | None |

    \\* The single-instrument-only-description row preserves the
    legacy heading behaviour (description renders as the H2 text)
    so operators who haven't migrated to ``short_label`` yet don't
    silently lose their per-instrument context. The spec's strict
    reading was "no heading; description shown elsewhere", but
    there's no other display path for ``Instrument.description``
    today; preserving it here is a small spec deviation in service
    of operator continuity.
    """

    title: str | None
    subtitle: str | None


def page_button_label(instrument: Instrument, position: int) -> str:
    """Label for a Page N button on the reviewer surface's action row.

    Returns ``"Page #{N}: {short_label}"`` when the operator has set
    ``Instrument.short_label`` (32-char ceiling enforced at the
    schema layer per Segment 11L); falls back to bare ``"Page #{N}"``
    otherwise.
    """
    short = (instrument.short_label or "").strip()
    if short:
        return f"Page #{position}: {short}"
    return f"Page #{position}"


def instrument_heading(
    *, instrument: Instrument, position: int, total_count: int
) -> InstrumentHeading:
    """Build the per-instrument heading title + subtitle for the
    reviewer surface, per the composition table on
    :class:`InstrumentHeading`.
    """
    short = (instrument.short_label or "").strip()
    desc = (instrument.description or "").strip() or None
    if total_count == 1:
        if short:
            return InstrumentHeading(title=short, subtitle=desc)
        if desc:
            # Legacy behaviour preserved — see the docstring's note.
            return InstrumentHeading(title=desc, subtitle=None)
        return InstrumentHeading(title=None, subtitle=None)
    # Multi-instrument: position prefix is the safety-net default.
    if short:
        return InstrumentHeading(title=f"Page #{position}: {short}", subtitle=desc)
    return InstrumentHeading(title=f"Page #{position}", subtitle=desc)


@dataclass(frozen=True)
class PageButton:
    """View-shape for a Page button on the reviewer-surface action row."""

    position: int
    label: str
    href: str
    is_current: bool


def placeholder_for_field(field: InstrumentResponseField) -> str:
    """Short hint shown inside the input box when empty, so reviewers
    know what shape a value should take. Mirrors the RTD's validation
    block; returns ``""`` for List rows or when the validation block is
    incomplete (e.g. an Integer RTD missing ``step``)."""
    validation = field.validation or {}
    data_type = field.data_type
    if data_type == "String":
        max_length = validation.get("max_length")
        if max_length is None:
            return ""
        min_length = validation.get("min_length") or 0
        return f"{int(min_length)} to {int(max_length)} char"
    if data_type in ("Integer", "Decimal"):
        min_ = validation.get("min")
        max_ = validation.get("max")
        step = validation.get("step")
        if min_ is None or max_ is None or step is None:
            return ""
        if data_type == "Integer":
            return (
                f"{int(min_)} to {int(max_)}, steps of {int(step)}"
            )
        return f"{min_:.1f} to {max_:.1f}, steps of {step:.1f}"
    return ""


def constraint_summary_for_field(field: InstrumentResponseField) -> str:
    """Short ``min-max[, steps of step]`` summary used in the
    above-table constraint row on the reviewer surface. Distinct from
    ``placeholder_for_field`` (``a to b``) — this one uses the dash
    notation requested for the summary line. Returns ``""`` when the
    validation block is incomplete or absent."""
    validation = field.validation or {}
    data_type = field.data_type
    if data_type == "String":
        max_length = validation.get("max_length")
        if max_length is None:
            return ""
        min_length = validation.get("min_length") or 0
        return f"{int(min_length)}-{int(max_length)} char"
    if data_type in ("Integer", "Decimal"):
        min_ = validation.get("min")
        max_ = validation.get("max")
        step = validation.get("step")
        if min_ is None or max_ is None or step is None:
            return ""
        if data_type == "Integer":
            return f"{int(min_)}-{int(max_)}, steps of {int(step)}"
        return f"{min_:.1f}-{max_:.1f}, steps of {step:.1f}"
    # List rows are omitted from the constraint summary — the
    # ``<select>`` already constrains the choice in the input itself.
    return ""


def _bulk_state(values: list[bool]) -> str:
    """Three-state value for a bulk toggle: ``all-on`` / ``all-off`` / ``mixed``."""
    if not values:
        return "all-off"
    on = sum(1 for v in values if v)
    if on == 0:
        return "all-off"
    if on == len(values):
        return "all-on"
    return "mixed"


@dataclass(frozen=True)
class InstrumentRulePickerOption:
    """One row in the per-card Assignment Rule picker's `<select>`.

    Mirrors :class:`app.web.views._rule_builder.RuleBasedSelectorOption`
    in shape but is keyed on ``session_rule_sets.id`` (not the
    operator-tier id) because the picker writes that id to
    ``instruments.rule_set_id``.
    """

    id: int
    name: str
    description: str
    eligible_pair_count: int
    is_seeded: bool


@dataclass(frozen=True)
class InstrumentRulePickerContext:
    """Per-instrument context for the Assignment Rule sub-card.

    ``selected_rule_set_id`` is the instrument's current pin (``None``
    means the operator hasn't pinned anything yet — picker renders
    the "— No rule —" sentinel option pre-selected). ``options`` is
    the same list for every card on the page (the visible session
    RuleSets); the per-card variation lives in
    ``selected_rule_set_id`` + ``selected_eligible_pair_count`` +
    ``open_rule_builder_url``.
    """

    options: list[InstrumentRulePickerOption]
    selected_rule_set_id: int | None
    selected_eligible_pair_count: int
    open_rule_builder_url: str


def _build_rule_picker_options(
    db: Session, review_session: ReviewSession
) -> tuple[list[InstrumentRulePickerOption], dict[int, int]]:
    """Compute the picker option list + a per-rule eligibility-count
    map (``rule_set_id -> N pairs``) once per page load.

    Each option is the result of running the rule engine against the
    session's current reviewer / reviewee populations, mirroring the
    pre-15B Rule Based card pattern. The map lets per-instrument
    contexts read the count for the currently-pinned rule without a
    second engine pass.

    Returns ``([], {})`` on rosters that produce no candidate pairs;
    eligibility is then 0 for every option.
    """
    from app.schemas.rules import (
        Combinator,
        Rule,
        RuleSetOptions,
        RuleSetScope,
        RuleSetSchema,
    )
    from app.services import assignments as assignments_service
    from app.services import relationships as relationships_service
    from app.services.rules import engine, session_library
    from pydantic import TypeAdapter

    rule_adapter = TypeAdapter(Rule)
    rule_sets = session_library.list_visible_session_rule_sets(
        db, session_id=review_session.id
    )
    if not rule_sets:
        return [], {}

    reviewers = assignments_service.list_reviewers(db, review_session.id)
    reviewees = assignments_service.list_reviewees(db, review_session.id)
    pair_context_lookup = relationships_service.pair_context_lookup(
        db, review_session.id
    )

    options: list[InstrumentRulePickerOption] = []
    eligibility_by_id: dict[int, int] = {}
    for row in rule_sets:
        try:
            schema = RuleSetSchema(
                id=row.id,
                name=row.name,
                description=row.description or "",
                scope=RuleSetScope.personal,
                combinator=Combinator(row.combinator),
                rules=[
                    rule_adapter.validate_python(payload)
                    for payload in row.rules_json
                ],
                options=RuleSetOptions(
                    excludeSelfReviews=row.exclude_self_reviews,
                    seed=row.seed,
                ),
            )
            result = engine.evaluate(
                schema,
                reviewers=reviewers,
                reviewees=reviewees,
                revision_seed=row.id,
                pair_context_lookup=pair_context_lookup,
            )
            count = len(result.pairs)
        except Exception:
            count = 0
        eligibility_by_id[row.id] = count
        options.append(
            InstrumentRulePickerOption(
                id=row.id,
                name=row.name,
                description=row.description or "",
                eligible_pair_count=count,
                is_seeded=row.is_seeded,
            )
        )
    return options, eligibility_by_id


def build_instrument_rule_picker_contexts(
    db: Session,
    review_session: ReviewSession,
    instruments: list[Instrument],
) -> dict[int, InstrumentRulePickerContext]:
    """One :class:`InstrumentRulePickerContext` per instrument, keyed
    by ``instrument.id``. The option list + eligibility map are shared
    across cards on the page — only the selected id + Rule Builder
    deep-link vary per instrument.
    """
    options, eligibility_by_id = _build_rule_picker_options(
        db, review_session
    )
    contexts: dict[int, InstrumentRulePickerContext] = {}
    for instrument in instruments:
        selected_id = instrument.rule_set_id
        selected_count = (
            eligibility_by_id.get(selected_id, 0)
            if selected_id is not None
            else 0
        )
        builder_url = (
            f"/operator/sessions/{review_session.id}"
            f"/assignments/rule-based-editor"
            f"?instrument_id={instrument.id}"
        )
        if selected_id is not None:
            builder_url += f"&rule_set_id={selected_id}"
        contexts[instrument.id] = InstrumentRulePickerContext(
            options=options,
            selected_rule_set_id=selected_id,
            selected_eligible_pair_count=selected_count,
            open_rule_builder_url=builder_url,
        )
    return contexts


def build_instruments_context(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    editing: int | None = None,
    saved: int | None = None,
    rtd_error: str | None = None,
    rtd_id: int | None = None,
    rf_save_error: str | None = None,
    editing_rtd_id: int | None = None,
    rtd_delete_blocked_id: int | None = None,
    rtd_delete_blocked_rfs: int | None = None,
    rtd_delete_blocked_instruments: int | None = None,
    rtd_delete_blocked_responses: int | None = None,
    rtd_delete_blocked_assignments: int | None = None,
    rtd_would_empty_id: int | None = None,
    rtd_would_empty_instruments: str | None = None,
    sort_save_error: str | None = None,
    sort_save_error_instrument_id: int | None = None,
) -> dict[str, Any]:
    """Build the template context for the operator instruments index.

    Runs the per-request idempotent display-field / RTD backfills
    (locked-row safety net + lazy seeds + stale-row prune + RTD seed),
    derives the editing-state machine, and packages the URL-driven
    error / cascade query params into the dict the template expects.
    Commits the backfill side-effects before returning so subsequent
    queries see the seeded rows.
    """
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    # Make sure every instrument has its locked Name / Email Display
    # Fields rows. The Alembic migration backfills existing instruments;
    # this is the per-request safety net for any sessions that slip
    # through (e.g. created before the migration ran).
    for instrument in instruments:
        instruments_service.ensure_locked_display_fields(
            db, instrument=instrument
        )
    # Prune Display Fields rows whose underlying data source no longer
    # has any populated value (locked Name / Email rows are exempt and
    # always kept). Runs before the lazy seeds so the canonical seed
    # order — reviewee.* before pair_context.* — falls out naturally:
    # any stale rows are gone, then the seeds append fresh in the
    # canonical sequence.
    instruments_service.prune_unpopulated_display_fields(db, review_session)
    # Per-request idempotent backfill of the lazy-seeded display
    # fields. The reviewee / assignment imports already trigger these
    # in the happy path; calling them on every GET catches sessions
    # whose roster or assignments were imported before the lazy-seed
    # logic landed (PR #203). Cheap — both helpers short-circuit when
    # there's nothing to seed.
    instruments_service.seed_display_fields_from_reviewees(db, review_session)
    instruments_service.seed_display_fields_from_assignments(db, review_session)
    # Idempotent per-request backfill of the seeded RTD catalog.
    # Existing sessions get the rows from the Slice 4a migration; this
    # call covers any session created without going through
    # ``ensure_default_instrument`` (e.g. raw fixtures in tests).
    instruments_service.ensure_default_response_type_definitions(
        db, review_session
    )
    db.commit()

    is_ready = lifecycle.is_ready(review_session)
    can_edit = not is_ready
    # State machine: ``?editing={instrument_id}`` opens that card for
    # editing. The yellow lock card on a ``ready`` session overrides
    # everything — every per-instrument card stays locked.
    editing_instrument_id = None if is_ready else editing
    # Slice 4d: the per-instrument editing state and the RTD editing
    # state are mutually exclusive — one editing context on the page
    # at a time. If both URL params are set (e.g. via a stale link),
    # the per-instrument card wins; the RTD card stays locked.
    effective_editing_rtd_id: int | None = None
    if not is_ready and editing_instrument_id is None:
        effective_editing_rtd_id = editing_rtd_id

    # "Saved" / "not saved" pill on each per-instrument card's status
    # sub-card. An instrument is "saved" if it has at least one audit
    # event indicating an operator-driven persistence of its field
    # tables (display fields saved via bulk save, edit, add, delete,
    # or move). Pure draft instruments — only seeded rows, never
    # touched — render as "not saved".
    instrument_saved_state = instruments_service.saved_state_for_session(
        db, session_id=review_session.id
    )
    rtds = instruments_service.get_session_rtds(
        db, session_id=review_session.id
    )
    # 15C Slice 3: library RTDs the operator hasn't already pulled
    # into this session — drives the "Add from library" picker on
    # the RTD card. Empty list means either no library entries or
    # every library entry is already in this session.
    library_rtds_available = instruments_service.list_library_rtds_not_in_session(
        db, owner_user=user, session_id=review_session.id
    )

    rtd_delete_blocked = (
        {
            "id": rtd_delete_blocked_id,
            "response_field_count": rtd_delete_blocked_rfs or 0,
            "instrument_count": rtd_delete_blocked_instruments or 0,
            "response_count": rtd_delete_blocked_responses or 0,
            "assignment_count": rtd_delete_blocked_assignments or 0,
        }
        if rtd_delete_blocked_id is not None
        else None
    )
    rtd_would_empty = (
        {
            "id": rtd_would_empty_id,
            "instrument_numbers": [
                n for n in (rtd_would_empty_instruments or "").split(",") if n
            ],
        }
        if rtd_would_empty_id is not None
        else None
    )

    rule_picker_by_instrument_id = build_instrument_rule_picker_contexts(
        db, review_session, instruments
    )

    return {
        "user": user,
        "session": review_session,
        "status_pills": session_status_pills(db, review_session),
        "instruments": instruments,
        "rule_picker_by_instrument_id": rule_picker_by_instrument_id,
        "is_ready": is_ready,
        "can_edit": can_edit,
        "bulk_accepting_state": _bulk_state(
            [i.accepting_responses for i in instruments]
        ),
        "bulk_visibility_state": _bulk_state(
            [i.responses_visible_when_closed for i in instruments]
        ),
        "editing_instrument_id": editing_instrument_id,
        "instrument_saved_state": instrument_saved_state,
        "saved_instrument_id": saved,
        "rtds": rtds,
        "library_rtds_available": library_rtds_available,
        "rtd_error": rtd_error,
        "rtd_error_id": rtd_id,
        "rf_save_error": rf_save_error,
        "editing_rtd_id": effective_editing_rtd_id,
        "is_some_instrument_editing": editing_instrument_id is not None,
        "is_some_rtd_unlocked": effective_editing_rtd_id is not None,
        "rtd_delete_blocked": rtd_delete_blocked,
        "rtd_would_empty": rtd_would_empty,
        "sort_save_error": sort_save_error,
        "sort_save_error_instrument_id": sort_save_error_instrument_id,
        "breadcrumbs": breadcrumbs.operator_session_child(
            review_session, "Instruments"
        ),
    }
