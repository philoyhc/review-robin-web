"""The Instruments card's intro layout chip (segment 19Y Item 1): a cycle
chip beside "Preview review instrument" reading "Layout 1" / "Layout 2".
Layout 1 (the default) puts the heading and help cards left and the
visibility card right; Layout 2 the heading and visibility left and the
help cards right. Narrow, both stack heading, visibility, help.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Locator, Page, expect

from ._builder import (
    REVIEWER_EMAIL,
    activate,
    open_card,
    open_unlocked,
    save,
    seed_rosters,
    session_pk,
)
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


def _hide_help_text(database_url: str, session_id: str) -> None:
    """No help card at all: every response field's help text hidden."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument, InstrumentResponseField

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            for field in db.execute(
                select(InstrumentResponseField)
                .join(Instrument, Instrument.id == InstrumentResponseField.instrument_id)
                .where(Instrument.session_id == session_pk(database_url, session_id))
            ).scalars():
                field.help_text_visible = False
            db.commit()
    finally:
        engine.dispose()


def _describe_instrument(database_url: str, session_id: str) -> None:
    """A description, so the reviewer surface draws a heading card."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            instrument = db.execute(
                select(Instrument).where(
                    Instrument.session_id == session_pk(database_url, session_id)
                )
            ).scalar_one()
            instrument.description = "Peer review"
            db.commit()
    finally:
        engine.dispose()


_BOXES = """intro => {
  const box = sel => {
    const el = intro.querySelector(sel);
    if (!el || !el.offsetParent) { return null; }
    const r = el.getBoundingClientRect();
    return {x: r.left, y: r.top, bottom: r.bottom};
  };
  return {
    heading: box('.rs-intro-name'),
    visibility: box('.rs-intro-visibility'),
    help: box('.rs-help-card'),
  };
}"""


def _boxes(card: Locator) -> dict[str, dict[str, float] | None]:
    """Where the preview's intro cards sit; ``None`` for one not drawn."""
    return card.locator("[data-new-model-band2-intro-card]").evaluate(_BOXES)


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
    # ``aria-disabled`` makes Playwright refuse the click; a person's
    # still reaches the handler, which is what this pins.
    chip.click(force=True)
    expect(chip).to_have_text("Layout 1")
    expect(card.locator("[data-intro-layout-input]")).to_have_value("layout_1")


def test_with_no_help_card_layout_1_keeps_one_column(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """No help card: the heading and visibility stay stacked in the left
    column, as today, whatever the layout."""
    session_id = new_session()
    _hide_help_text(live_server.database_url, session_id)
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    expect(card.locator("[data-intro-layout-chip]")).to_have_text("Layout 1")
    boxes = _boxes(card)
    assert boxes["help"] is None, boxes
    assert boxes["visibility"]["x"] == boxes["heading"]["x"], boxes
    assert boxes["visibility"]["y"] >= boxes["heading"]["bottom"], boxes


def test_a_locked_preview_without_a_heading_lifts_the_help_cards(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """Locked, an empty heading card is not drawn; in Layout 1 the help
    cards then start level with the visibility card, not one gap lower."""
    session_id = new_session()
    _give_a_field_help_text(live_server.database_url, session_id)
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_card(page, session_id)
    expect(card).to_have_attribute("data-instrument-locked", "true")
    expect(card.locator("[data-new-model-band2-intro-card] .rs-help-card").first).to_be_visible()
    boxes = _boxes(card)
    assert boxes["heading"] is None, boxes
    assert boxes["help"]["y"] == boxes["visibility"]["y"], boxes
    assert boxes["help"]["x"] < boxes["visibility"]["x"], boxes


def test_the_reviewer_surface_takes_the_instruments_layout(
    page: Page,
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """The reviewer meets the same arrangement: Layout 1 by default, with
    no heading card (a lone untitled instrument) and with one."""
    session_id = new_session()
    seed_rosters(api, session_id)
    _give_a_field_help_text(live_server.database_url, session_id)
    activate(api, live_server.database_url, session_id)
    reviewer = page_as(REVIEWER_EMAIL)
    reviewer.goto(f"/me/sessions/{session_id}")
    intro = reviewer.locator(".rs-intro-columns").first
    expect(intro).to_have_attribute("data-intro-layout", "layout_1")
    boxes = intro.evaluate(_BOXES)
    assert boxes["heading"] is None, boxes
    assert boxes["help"]["y"] == boxes["visibility"]["y"], boxes
    assert boxes["help"]["x"] < boxes["visibility"]["x"], boxes

    _describe_instrument(live_server.database_url, session_id)
    reviewer.reload()
    boxes = reviewer.locator(".rs-intro-columns").first.evaluate(_BOXES)
    assert boxes["help"]["x"] == boxes["heading"]["x"], boxes
    assert boxes["help"]["y"] >= boxes["heading"]["bottom"], boxes
    assert boxes["visibility"]["x"] > boxes["help"]["x"], boxes


def test_the_chip_leaves_the_tab_order_while_locked(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    card = open_card(page, session_id)
    chip = card.locator("[data-intro-layout-chip]")
    expect(chip).to_have_attribute("aria-disabled", "true")
    expect(chip).not_to_have_attribute("tabindex", "0")
    card.locator("[data-instrument-unlock-toggle]:visible").first.click()
    expect(card).to_have_attribute("data-instrument-locked", "false")
    expect(chip).to_have_attribute("tabindex", "0")
    expect(chip).not_to_have_attribute("aria-disabled", "true")
