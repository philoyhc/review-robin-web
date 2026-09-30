"""19T Item 16 entry 6 — Band 2's intro card shows the reviewer
surface's heading (``views.instrument_heading``): no ``#1:`` in a
one-instrument session, the description in the title's place when there
is no short label, and no blank subtitle line when there is no
description. The browser's copy of the rule, ``newModelIntroHeading``,
is held to the same answers by ``test_inline_scripts_parse.py``."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument

from .test_instrument_builder_routes import _make_session, _new_model_with_tags


def _name_card(client: TestClient, session_id: int, instrument_id: int) -> str:
    flat = " ".join(
        client.get(f"/operator/sessions/{session_id}/instruments").text.split()
    )
    intro = flat[flat.index(f'data-instrument-id="{instrument_id}"') :]
    start = intro.index('<div class="card rs-instrument-card rs-intro-name"')
    return intro[start : intro.index("data-intro-description-input", start)]


def _only_instrument(db: Session, session_id: int) -> Instrument:
    return db.execute(
        select(Instrument).where(Instrument.session_id == session_id)
    ).scalar_one()


def test_one_instrument_has_no_position_prefix(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, code="b2-head-one")
    instrument = _only_instrument(db, review_session.id)
    instrument.short_label = "Group Peer Review"
    instrument.description = None
    db.commit()
    card = _name_card(client, review_session.id, instrument.id)
    assert "<h2 data-intro-title-view>Group Peer Review</h2>" in card
    assert "#1" not in card
    # No description: the subtitle is hidden, not a blank line.
    assert "data-intro-description-view data-lock-only hidden></p>" in card
    assert "min-height" not in card
    assert "data-intro-empty" not in card


def test_one_instrument_without_a_label_titles_its_description(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="b2-head-desc")
    instrument = _only_instrument(db, review_session.id)
    instrument.short_label = None
    instrument.description = "Rate each teammate."
    db.commit()
    card = _name_card(client, review_session.id, instrument.id)
    assert "<h2 data-intro-title-view>Rate each teammate.</h2>" in card
    assert "data-intro-description-view data-lock-only hidden></p>" in card


def test_one_instrument_with_neither_is_an_empty_card(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="b2-head-none")
    instrument = _only_instrument(db, review_session.id)
    instrument.short_label = None
    instrument.description = None
    db.commit()
    card = _name_card(client, review_session.id, instrument.id)
    # Locked, the page's CSS hides a card marked empty, as the reviewer
    # surface renders no heading card.
    assert "data-intro-empty" in card
    assert "<h2 data-intro-title-view hidden></h2>" in card


def test_several_instruments_keep_the_position(client: TestClient, db: Session) -> None:
    review_session, new_model = _new_model_with_tags(client, db, code="b2-head-many")
    new_model.short_label = "Peer Review"
    new_model.description = "Your impression."
    db.commit()
    card = _name_card(client, review_session.id, new_model.id)
    assert "<h2 data-intro-title-view>#2: Peer Review</h2>" in card
    assert "data-intro-description-view data-lock-only>Your impression.</p>" in card
