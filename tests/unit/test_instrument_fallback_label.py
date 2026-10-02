"""D13 (2026-10-02): an extract's ``Instrument_{N}`` fallback is the
instrument's ``session_seq`` — the handle the operator pages show —
not its display position, which a reorder changes."""
from __future__ import annotations

from app.db.models import Instrument
from app.services.extracts import entity_metadata_extract
from app.services.extracts.by_instrument_extract import (
    by_instrument_filename_slug,
    fallback_instrument_label,
)


def test_the_fallback_is_the_session_seq_not_the_position() -> None:
    instrument = Instrument(session_id=1, name="Peer", order=0, session_seq=7)

    assert fallback_instrument_label(instrument, position=2) == "Instrument_7"
    assert by_instrument_filename_slug(instrument, 2, used=set()) == "Instrument_7"
    assert (
        entity_metadata_extract._instrument_short_or_fallback(instrument, 2)
        == "Instrument_7"
    )


def test_a_short_label_still_wins() -> None:
    instrument = Instrument(
        session_id=1, name="Peer", order=0, session_seq=7, short_label="Peer"
    )

    assert fallback_instrument_label(instrument, position=2) == "Peer"


def test_a_label_that_sanitises_to_nothing_falls_back_to_the_session_seq() -> None:
    instrument = Instrument(
        session_id=1, name="Peer", order=0, session_seq=7, short_label="!!!"
    )

    assert by_instrument_filename_slug(instrument, 2, used=set()) == "Instrument_7"
