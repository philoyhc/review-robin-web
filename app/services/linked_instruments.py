"""A linked application's instrument (segment 23F rung 7a,
`guide/segment_23F_linked_drafts.md`, *Instruments decided*).

One instrument per gate: a gate filters to one set of pairwise
assignments, which its application sends as the Relationships file. So
Review Robin fixes the instrument's assignment rule itself rather than
taking it from the bundle: Link 1 *All*, Link 2 a rule that keeps a pair
whose relationship tag is filled (``pair_context.tag1 IS FILLED``, in
effect: assign where a relationship exists), Link 3 *Individual*. The
application fills the tag on every relationship it sends (with the
evaluator's source), so every pair it sends is kept.

At the create the instrument's display fields start from the reviewee's
name and key (Review Robin's fixed pair) and the dossier link
(``ProfileLink``); from then on they are the operator's.

A re-send carries the instrument's rows the application owns (rung 7b):
its name (the gate's, which the short label follows) and description,
and its response fields in the application's order. Layout, widths and
color stay Review Robin's.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, InstrumentDisplayField, ReviewSession, User
from app.json_shapes import json_list
from app.services import audit
from app.services import instruments as instruments_service
from app.services.instruments import record_band1_links_set
from app.services.session_config_io import InstrumentSpec, ResponseFieldSpec

#: Link 2's one rule: keep the pairs whose relationship carries a tag.
PAIR_RULE = {
    "field": "pair_context.tag1",
    "op": "IS FILLED",
    "operand_value": "",
    "operand_tag": "",
}
#: The dossier link, the one display field beside the fixed pair.
PROFILE_LINK = ("reviewee", "profile_link")


#: The instrument rows a re-send may carry: the gate's name and
#: description, and each response field's definition (no branching).
_INSTRUMENT_ROW = re.compile(r"^instruments\[1\]\.(name|description)$")
_FIELD_ROW = re.compile(
    r"^instruments\[1\]\.response_fields\[\d+\]\."
    r"(field_key|label|response_type|data_type|min|max|step|list_csv"
    r"|required|help_text|help_text_visible|visible)$"
)
#: The short label's cap (``Instrument.short_label``).
SHORT_LABEL_MAX = 32


class NotOneInstrument(ValueError):
    """A linked application's draft holds other than one instrument."""


def owns_row(field: str) -> bool:
    """Whether a Settings row is one of the instrument rows a linked
    application owns."""
    return bool(_INSTRUMENT_ROW.match(field) or _FIELD_ROW.match(field))


def row_errors(spec: InstrumentSpec, rows: frozenset[str]) -> list[str]:
    """What the import's checks leave to this: every sent field names its
    data type, since a linked field has no default to fall back on, and
    its bounds pass the card's shape rule (Codex on #3926)."""
    if not any(".response_fields[" in row for row in rows):
        return []
    errors: list[str] = []
    for m, field in sorted(spec.response_fields.items()):
        at = f"instruments[1].response_fields[{m}]"
        if not field.data_type:
            errors.append(f"{at}.data_type: data_type is required")
            continue
        shape = instruments_service.response_field_shape_error(
            field.data_type, field.min, field.max, field.step, field.list_csv
        )
        if shape:
            errors.append(f"{at}: {shape}")
    return errors


def the_instrument(db: Session, review_session: ReviewSession) -> Instrument:
    """The draft's one instrument, or :class:`NotOneInstrument`."""
    instruments = list(
        db.scalars(select(Instrument).where(Instrument.session_id == review_session.id))
    )
    if len(instruments) != 1:
        raise NotOneInstrument(
            f"A linked application's session holds one instrument, not {len(instruments)}."
        )
    return instruments[0]


def fix_rule(db: Session, instrument: Instrument, *, actor: User) -> None:
    """Set the fixed assignment rule, through the service the Instruments
    page saves Band 1 with, each link marked set."""
    instruments_service.set_band1_assignment_rules(
        db,
        instrument=instrument,
        link1_mode="all",
        link1_combinator="AND",
        link1_rules=[],
        link2_mode="filter",
        link2_combinator="AND",
        link2_rules=[dict(PAIR_RULE)],
        actor=actor,
        touched_links={"link1", "link2"},
        link3_mode="individual",
    )
    instruments_service.set_unit_of_review(
        db, instrument=instrument, mode="individual", boundary_pairs=[], actor=actor, touched=True
    )
    before = list(instrument.band1_touched_links or [])
    if "link3" not in before:
        instrument.band1_touched_links = sorted({*before, "link3"})
        record_band1_links_set(db, instrument, before=before, actor=actor)


def default_display_fields(db: Session, instrument: Instrument, *, actor: User) -> None:
    """Start the display fields from the fixed pair and the dossier link:
    every other field the rosters seeded is removed."""
    fields = list(
        db.scalars(
            select(InstrumentDisplayField).where(
                InstrumentDisplayField.instrument_id == instrument.id
            )
        )
    )
    present = {(f.source_type, f.source_field) for f in fields}
    for field in fields:
        pair = (field.source_type, field.source_field)
        if pair == PROFILE_LINK or instruments_service.is_locked_display_source(*pair):
            continue
        instruments_service.delete_display_field(db, field=field, actor=actor)
    if PROFILE_LINK not in present:
        instruments_service.add_display_field(
            db,
            instrument=instrument,
            source_type=PROFILE_LINK[0],
            source_field=PROFILE_LINK[1],
            label="",
            visible=True,
            actor=actor,
        )


def set_up(db: Session, review_session: ReviewSession, *, actor: User) -> Instrument:
    """The create's instrument set-up for a linked application that takes
    the instrument lock: its one instrument, the fixed rule, the display
    default. :class:`NotOneInstrument` when the draft holds other than one."""
    instrument = the_instrument(db, review_session)
    fix_rule(db, instrument, actor=actor)
    default_display_fields(db, instrument, actor=actor)
    # The short label follows the gate's name, as a re-send's does.
    if instrument.name:
        instruments_service.update_short_label(
            db,
            instrument=instrument,
            short_label=instrument.name.strip()[:SHORT_LABEL_MAX],
            actor=actor,
        )
    db.flush()
    return instrument


def _field_entry(field: ResponseFieldSpec) -> dict[str, Any]:
    return {
        "field_key": field.field_key,
        "label": field.label,
        "response_type": field.response_type,
        "data_type": field.data_type,
        "min": field.min,
        "max": field.max,
        "step": field.step,
        "list_csv": field.list_csv,
        "required": field.required,
        "help_text": field.help_text,
        "help_text_visible": field.help_text_visible,
        "visible": field.visible,
    }


def apply_owned(
    db: Session,
    review_session: ReviewSession,
    spec: InstrumentSpec,
    rows: frozenset[str],
    *,
    actor: User,
) -> None:
    """Write a re-send's instrument rows (``rows`` the paths it carried),
    inside the caller's unit: the name, with the short label following
    it; the description; and, when any field row is sent, the response
    fields replaced in the application's order
    (``instruments.replace_response_fields``).
    :class:`NotOneInstrument` when the draft holds other than one."""
    instrument = the_instrument(db, review_session)
    if "instruments[1].name" in rows and spec.name:
        name = spec.name.strip()
        if name != instrument.name:
            audit.write_event(
                db,
                event_type="instrument.renamed",
                summary=f"Renamed instrument {instrument.name!r} to {name!r} (linked re-send)",
                actor_user_id=actor.id,
                session=review_session,
                payload=audit.changes({"name": [instrument.name, name]}),
                refs={"instrument_id": instrument.id},
            )
            instrument.name = name
        instruments_service.update_short_label(
            db, instrument=instrument, short_label=name[:SHORT_LABEL_MAX], actor=actor
        )
    if "instruments[1].description" in rows:
        instruments_service.update_instrument_description(
            db, instrument=instrument, description=spec.description, actor=actor
        )
    if any(".response_fields[" in row for row in rows):
        instruments_service.replace_response_fields(
            db,
            instrument=instrument,
            fields=[_field_entry(f) for _, f in sorted(spec.response_fields.items())],
            actor=actor,
        )


def display_sources(db: Session, review_session: ReviewSession) -> set[tuple[str, str]]:
    """The one instrument's display-field sources, read before a re-send's
    rosters save; empty when the draft holds other than one."""
    try:
        instrument = the_instrument(db, review_session)
    except NotOneInstrument:
        return set()
    return {(f.source_type, f.source_field) for f in instrument.display_fields}


def keep_display_fields(
    db: Session, review_session: ReviewSession, before: set[tuple[str, str]], *, actor: User
) -> None:
    """Remove the display fields a re-send's reviewee save seeded since
    :func:`display_sources` read ``before``: from the create on they are
    the operator's (*Instruments decided*), so a re-send adds none (the
    cold read of 23F). Only flushes, for the caller's unit."""
    if not before:
        return
    instrument = the_instrument(db, review_session)
    db.refresh(instrument, ["display_fields"])
    for field in list(instrument.display_fields):
        source = (field.source_type, field.source_field)
        if source in before or instruments_service.is_locked_display_source(*source):
            continue
        instruments_service.delete_display_field(db, field=field, actor=actor)


def hold_profile(instrument: Instrument, state: dict[str, Any]) -> None:
    """Keep the dossier link's display selection as it stands in a Band 2
    save's ``state`` (author, 2026-11-16): on a linked instrument it is
    the application's, like the fixed pair, so the operator's tick neither
    adds nor removes it. A state without ``selected_display_keys`` leaves
    the selections alone already."""
    keys = json_list(state.get("selected_display_keys"))
    if keys is None:
        return
    key = ".".join(PROFILE_LINK)
    shown = any(
        (field.source_type, field.source_field) == PROFILE_LINK and field.visible
        for field in instrument.display_fields
    )
    # Compared as ``set_band2_state`` reads them, stripped, so a padded
    # key cannot slip past (Codex on #3932).
    held: list[object] = [k for k in keys if str(k).strip() != key]
    if shown:
        held.append(key)
    state["selected_display_keys"] = held
