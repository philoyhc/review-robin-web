"""The Instruments card's intro layout chip (segment 19Y Item 1): a cycle
chip beside "Preview review instrument" reading "Layout 1" / "Layout 2".
Layout 1 (the default) puts the heading and help cards left and the
visibility card right; Layout 2 the heading and visibility left and the
help cards right. Narrow, both stack heading, visibility, help.
"""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Locator, Page, expect

from ._builder import open_card, open_unlocked, save, session_pk
from .conftest import LiveServer


def _give_a_field_help_text(database_url: str, session_id: str) -> None:
    """A visible help card for certain, written directly: the preview
    builds its help cards from the response fields' help text."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument, InstrumentResponseField

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            field = db.execute(
                select(InstrumentResponseField)
                .join(Instrument, Instrument.id == InstrumentResponseField.instrument_id)
                .where(Instrument.session_id == session_pk(database_url, session_id))
                .order_by(InstrumentResponseField.order)
            ).scalars().first()
            field.help_text = "Score 1 to 5."
            field.help_text_visible = True
            db.commit()
    finally:
        engine.dispose()


def _boxes(card: Locator) -> dict[str, dict[str, float]]:
    return card.evaluate(
        """card => {
          const intro = card.querySelector('[data-new-model-band2-intro-card]');
          const box = sel => {
            const r = intro.querySelector(sel).getBoundingClientRect();
            return {x: r.left, y: r.top, bottom: r.bottom};
          };
          return {
            heading: box('.rs-intro-name'),
            visibility: box('.rs-intro-visibility'),
            help: box('.rs-help-card'),
          };
        }"""
    )


def test_the_chip_switches_the_preview_and_saves(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    _give_a_field_help_text(live_server.database_url, session_id)
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    chip = card.locator("[data-intro-layout-chip]")
    expect(chip).to_have_text("Layout 1")
    expect(
        card.locator("[data-new-model-band2-intro-card] .rs-help-card").first
    ).to_be_visible()

    boxes = _boxes(card)
    assert boxes["visibility"]["x"] > boxes["help"]["x"], boxes
    assert boxes["help"]["x"] == boxes["heading"]["x"], boxes
    assert boxes["help"]["y"] >= boxes["heading"]["bottom"], boxes

    chip.click()
    expect(chip).to_have_text("Layout 2")
    expect(card.locator("[data-new-model-band2-intro-card]")).to_have_attribute(
        "data-intro-layout", "layout_2"
    )
    boxes = _boxes(card)
    assert boxes["help"]["x"] > boxes["visibility"]["x"], boxes
    assert boxes["visibility"]["x"] == boxes["heading"]["x"], boxes
    save(page, card)

    card = open_unlocked(page, session_id)
    expect(card.locator("[data-intro-layout-chip]")).to_have_text("Layout 2")
    expect(card.locator("[data-intro-layout-input]")).to_have_value("layout_2")


def test_narrow_both_layouts_stack_heading_visibility_help(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    _give_a_field_help_text(live_server.database_url, session_id)
    page.set_viewport_size({"width": 700, "height": 1000})
    card = open_unlocked(page, session_id)
    chip = card.locator("[data-intro-layout-chip]")
    for label in ("Layout 1", "Layout 2"):
        expect(chip).to_have_text(label)
        boxes = _boxes(card)
        assert (
            boxes["heading"]["y"] < boxes["visibility"]["y"] < boxes["help"]["y"]
        ), (label, boxes)
        chip.click()


def test_a_locked_cards_chip_is_a_plain_pill_that_does_not_cycle(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    card = open_card(page, session_id)
    expect(card).to_have_attribute("data-instrument-locked", "true")
    chip = card.locator("[data-intro-layout-chip]")
    expect(chip).to_have_text("Layout 1")
    assert chip.evaluate("el => getComputedStyle(el).cursor") == "default"
    chip.click()
    expect(chip).to_have_text("Layout 1")
    expect(card.locator("[data-intro-layout-input]")).to_have_value("layout_1")
