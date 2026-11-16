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
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, InstrumentDisplayField, ReviewSession, User
from app.services import instruments as instruments_service
from app.services.instruments import record_band1_links_set

#: Link 2's one rule: keep the pairs whose relationship carries a tag.
PAIR_RULE = {
    "field": "pair_context.tag1",
    "op": "IS FILLED",
    "operand_value": "",
    "operand_tag": "",
}
#: The dossier link, the one display field beside the fixed pair.
PROFILE_LINK = ("reviewee", "profile_link")


class NotOneInstrument(ValueError):
    """A linked application's draft holds other than one instrument."""


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
    db.flush()
    return instrument
