"""Shared state read by every instruments-service slice.

Owns ``saved_state_for_session`` — the per-instrument "field tables
have been saved by the operator" lookup that drives the status pill
on the operator's Instruments page sub-cards. Read by ``views.py``
and by every slice in this package, hence its top-level home.

Per ``guide/archive/major_refactor.md`` §12.A, the slice modules
(``_rtds.py``, ``_display_fields.py``, ``_response_fields.py``,
``_instrument_crud.py``) import from this module but never the
other way round — same import-graph invariant the
``routes_operator/_shared.py`` carries.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument

# Audit-event types that signal "this instrument's field tables were
# saved by the operator" — used by ``saved_state_for_session`` to
# render the per-instrument-card status pill.
_SAVED_STATE_EVENT_TYPES: frozenset[str] = frozenset({
    "instrument.display_fields_saved",
    "instrument.display_field_added",
    "instrument.display_field_updated",
    "instrument.display_field_deleted",
    "instrument.display_field_moved",
    "instrument.field_added",
    "instrument.field_updated",
    "instrument.field_deleted",
    "instrument.fields_reordered",
    "instrument.response_fields_saved",
})


def _instrument_label(instrument: Instrument) -> str:
    """Operator-facing label for an instrument.

    Returns ``short_label`` when the operator has set one, else the
    ugly fallback ``"Instrument_{id}"`` that nudges the operator to
    set a proper short label. Used by audit-event copy, validation
    error messages, and operator-page UI sites that need a stable
    human-readable handle for an instrument.

    Per the 2026-05-28 operator-identifier policy (see
    ``spec/instruments.md`` "Identifiers"): the ``#`` prefix is
    reserved for reviewer-facing position numbering
    (``#{N}: {short_label}``); operator-facing UI uses short_label
    with the ``Instrument_{id}`` fallback. ``description`` and the
    auto-generated ``name`` handle no longer participate in the
    chain — ``description`` is reviewer-instructional copy and
    shouldn't silently become an operator label; ``name`` is now
    a pure internal handle.

    Lifted to ``_state.py`` in PR 2 of the §12.A ladder so display-
    fields / response-fields / instrument-CRUD slices can all reach
    it without a slice-to-slice import cycle.
    """
    short = (instrument.short_label or "").strip()
    if short:
        return short
    return f"Instrument_{instrument.id}"


def saved_state_for_session(
    db: Session, *, session_id: int
) -> dict[int, bool]:
    """Map ``instrument_id`` → True if the instrument has any audit
    event indicating an operator-driven save of its field tables; False
    otherwise. Instruments with no qualifying audit history render as
    "not saved" on the operator's status sub-card."""
    rows = db.execute(
        select(AuditEvent.event_type, AuditEvent.detail)
        .where(AuditEvent.session_id == session_id)
        .where(AuditEvent.event_type.in_(_SAVED_STATE_EVENT_TYPES))
    ).all()
    saved: dict[int, bool] = {}
    for event_type, detail in rows:
        if not detail:
            continue
        # Canonical shape (Segment 11K PR 2): refs.instrument_id.
        # Pre-migration rows kept the id at the top level.
        refs = detail.get("refs") or {}
        instrument_id = refs.get("instrument_id")
        if instrument_id is None:
            instrument_id = detail.get("instrument_id")
        if isinstance(instrument_id, int):
            saved[instrument_id] = True
    return saved
