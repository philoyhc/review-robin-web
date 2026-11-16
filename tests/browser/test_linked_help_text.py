"""A linked application's help text stays its own (segment 23F rung 7c,
Codex on #3927): unlocking the card shows the text, never a box to edit
it, where a native card's help text becomes a textarea."""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Page, expect

from ._builder import give_a_field_help_text, open_unlocked, session_pk
from .conftest import LiveServer

_BOX = "[data-new-model-band2-intro-card] [data-help-card-textarea]"


def _link(database_url: str, session_id: str) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.db.models import ReviewSession

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            review_session = db.get(ReviewSession, session_pk(database_url, session_id))
            assert review_session is not None
            review_session.linked_app = "applydesk"
            db.commit()
    finally:
        engine.dispose()


def test_a_linked_cards_help_text_is_not_editable(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    give_a_field_help_text(live_server.database_url, session_id, "Apply Desk's help.")
    _link(live_server.database_url, session_id)
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    expect(card.locator("[data-new-model-band2-intro-card]")).to_contain_text("Apply Desk's help.")
    expect(card.locator(_BOX)).to_have_count(0)


def test_a_native_cards_help_text_is_editable(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    give_a_field_help_text(live_server.database_url, session_id, "Our help.")
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    expect(card.locator(_BOX).first).to_have_value("Our help.")
