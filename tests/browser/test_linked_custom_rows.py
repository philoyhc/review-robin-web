"""A custom linked instrument's Band 3 in a real Chromium (segment 23G
rung 3): the fields its application sent are held, their name, type,
visibility, help and delete fixed, while R, ▲ ▼ and + stay live, and a
field of Review Robin's own saves beside them. A locked instrument's
rows stay fixed whole, as 23F made them."""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Page, expect

from ._builder import names, open_unlocked, rows, save, session_pk
from .conftest import LiveServer


def _link_custom(database_url: str, session_id: str) -> list[str]:
    """Link the session to Apply Desk as a custom gate, its current
    fields held; the held keys, in order."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.db.models import ReviewSession

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            review_session = db.get(ReviewSession, session_pk(database_url, session_id))
            assert review_session is not None
            review_session.linked_app = "applydesk"
            (instrument,) = review_session.instruments
            instrument.linked_mode = "custom"
            keys = [f.field_key for f in sorted(instrument.response_fields, key=lambda f: f.order)]
            instrument.held_field_keys = keys
            db.commit()
            return keys
    finally:
        engine.dispose()


def test_held_rows_keep_their_definition_and_an_own_field_saves(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    held = _link_custom(live_server.database_url, session_id)
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    before = names(card)
    first = rows(card).first
    expect(first).to_have_attribute("data-new-model-rf-held", "true")
    expect(first.locator("[data-new-model-rf-name]")).to_have_attribute("readonly", "")
    expect(first.locator("[data-new-model-rf-data-type]")).to_be_disabled()
    expect(first.locator("[data-new-model-rf-delete]")).to_be_disabled()
    expect(first.locator("[data-new-model-rf-active]")).to_be_disabled()
    expect(first.locator("[data-new-model-rf-help-visible]")).to_be_disabled()
    # Whether it is required is Review Robin's.
    required = first.locator("[data-new-model-rf-required]")
    expect(required).to_be_enabled()
    was = required.get_attribute("data-required")
    required.click()
    expect(required).not_to_have_attribute("data-required", was or "")
    # A field of its own, added below the first and named.
    first.locator("[data-new-model-rf-add]").click()
    added = rows(card).nth(1)
    expect(added).not_to_have_attribute("data-new-model-rf-held", "true")
    added.locator("[data-new-model-rf-name]").fill("Familiarity")
    save(page, card)
    page.reload()
    card = open_unlocked(page, session_id)
    assert names(card) == [before[0], "Familiarity", *before[1:]]
    assert len(held) == len(before)


def test_a_locked_cards_rows_stay_fixed(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    from .test_linked_help_text import _link

    session_id = new_session()
    _link(live_server.database_url, session_id)
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    region = card.locator("[data-new-model-rf-rows]")
    expect(region).to_have_attribute("data-linked-fixed", "")
    expect(card.locator('[data-new-model-rf-held="true"]')).to_have_count(0)
