"""The Instruments card's intro layout chip (segment 19Y Item 1): a cycle
chip beside "Preview review instrument" reading "Layout 1" / "Layout 2".
Layout 1 (the default) puts the help texts as rows in the heading card,
left, and the visibility card right; Layout 2 the heading and visibility
left and one help card of rows right (Item 2). Narrow, Layout 1 stacks
the heading card over visibility; Layout 2 heading, visibility, help.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import httpx
from playwright.sync_api import Locator, Page, expect

from ._builder import (
    REVIEWER_EMAIL,
    activate,
    open_card,
    open_unlocked,
    rows,
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


def _show_one_empty_help_text(database_url: str, session_id: str) -> None:
    """One field's ≡ on but its help text empty; every other field's off."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument, InstrumentResponseField

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            fields = db.execute(
                select(InstrumentResponseField)
                .join(Instrument, Instrument.id == InstrumentResponseField.instrument_id)
                .where(Instrument.session_id == session_pk(database_url, session_id))
                .order_by(InstrumentResponseField.order)
            ).scalars().all()
            for field in fields:
                field.help_text_visible = False
            fields[0].help_text = ""
            fields[0].help_text_visible = True
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
  const box = el => {
    if (!el || !el.offsetParent) { return null; }
    const r = el.getBoundingClientRect();
    return {x: r.left, y: r.top, bottom: r.bottom};
  };
  const row = intro.querySelector('.rs-help-row');
  const home = row && row.offsetParent
    ? (row.closest('.rs-intro-name') ? 'heading'
       : row.closest('.rs-intro-help') ? 'card' : 'elsewhere')
    : null;
  return {
    heading: box(intro.querySelector('.rs-intro-name')),
    visibility: box(intro.querySelector('.rs-intro-visibility')),
    visibilityTitle: box(intro.querySelector('.rs-intro-visibility h3')),
    help: box(intro.querySelector('.rs-intro-help')),
    row: box(row),
    rowHome: home,
    rowCount: [...intro.querySelectorAll('.rs-help-row')]
      .filter(el => el.offsetParent).length,
  };
}"""


def _boxes(card: Locator) -> dict:
    """Where the preview's intro cards and first help row sit; ``None``
    for one not drawn. ``rowHome`` names the card holding the rows."""
    return card.locator("[data-new-model-band2-intro-card]").evaluate(_BOXES)


def test_the_chip_moves_the_help_rows_and_saves(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """Layout 1: the help rows sit in the heading card, the visibility
    card beside it. Layout 2: they move into one help card on the right,
    an unsaved edit in a row's textarea going with them."""
    session_id = new_session()
    _give_a_field_help_text(live_server.database_url, session_id)
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    chip = card.locator("[data-intro-layout-chip]")
    expect(chip).to_have_text("Layout 1")
    first_help = card.locator(
        "[data-new-model-band2-intro-card] [data-help-card-textarea]"
    ).first
    expect(first_help).to_be_visible()

    boxes = _boxes(card)
    assert boxes["rowHome"] == "heading", boxes
    assert boxes["help"] is None, boxes
    assert boxes["visibility"]["x"] > boxes["heading"]["x"], boxes
    assert boxes["visibility"]["y"] == boxes["heading"]["y"], boxes

    first_help.fill("Typed before the move.")
    chip.click()
    expect(chip).to_have_text("Layout 2")
    expect(card.locator("[data-new-model-band2-intro-card]")).to_have_attribute(
        "data-intro-layout", "layout_2"
    )
    boxes = _boxes(card)
    assert boxes["rowHome"] == "card", boxes
    assert boxes["help"]["x"] > boxes["visibility"]["x"], boxes
    assert boxes["visibility"]["x"] == boxes["heading"]["x"], boxes
    expect(
        card.locator("[data-new-model-band2-intro-card] [data-help-card-textarea]").first
    ).to_have_value("Typed before the move.")
    save(page, card)

    card = open_unlocked(page, session_id)
    expect(card.locator("[data-intro-layout-chip]")).to_have_text("Layout 2")
    expect(card.locator("[data-intro-layout-input]")).to_have_value("layout_2")
    assert _boxes(card)["rowHome"] == "card"


def test_the_help_toggle_shows_and_hides_a_row(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """Each field's ≡ in Band 3 still decides whether its row shows."""
    session_id = new_session()
    _give_a_field_help_text(live_server.database_url, session_id)
    card = open_unlocked(page, session_id)
    before = _boxes(card)["rowCount"]
    assert before >= 1
    toggle = rows(card).first.locator("[data-new-model-rf-help-visible]")
    toggle.click()
    assert _boxes(card)["rowCount"] == before - 1
    toggle.click()
    assert _boxes(card)["rowCount"] == before


def test_narrow_layout_1_keeps_the_heading_card_whole(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """Narrow: Layout 1 stacks the heading card, help rows inside it,
    over the visibility card (the author, 2026-10-20); Layout 2 stacks
    heading, visibility, then the help card."""
    session_id = new_session()
    _give_a_field_help_text(live_server.database_url, session_id)
    page.set_viewport_size({"width": 700, "height": 1000})
    card = open_unlocked(page, session_id)
    chip = card.locator("[data-intro-layout-chip]")
    expect(chip).to_have_text("Layout 1")
    boxes = _boxes(card)
    assert boxes["rowHome"] == "heading", boxes
    assert boxes["heading"]["y"] < boxes["visibility"]["y"], boxes
    assert boxes["row"]["bottom"] <= boxes["visibility"]["y"], boxes

    chip.click()
    expect(chip).to_have_text("Layout 2")
    boxes = _boxes(card)
    assert boxes["rowHome"] == "card", boxes
    assert boxes["heading"]["y"] < boxes["visibility"]["y"] < boxes["help"]["y"], boxes


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


def test_with_no_help_row_layout_1_keeps_visibility_right(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """No help row (the author, 2026-10-20): Layout 1 keeps the heading
    left and the visibility card right, level with it; Layout 2 stacks
    them in the left column and draws no help card."""
    session_id = new_session()
    _hide_help_text(live_server.database_url, session_id)
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    chip = card.locator("[data-intro-layout-chip]")
    expect(chip).to_have_text("Layout 1")
    boxes = _boxes(card)
    assert boxes["rowCount"] == 0 and boxes["help"] is None, boxes
    assert boxes["visibility"]["x"] > boxes["heading"]["x"], boxes
    assert boxes["visibility"]["y"] == boxes["heading"]["y"], boxes

    chip.click()
    expect(chip).to_have_text("Layout 2")
    boxes = _boxes(card)
    assert boxes["help"] is None, boxes
    assert boxes["visibility"]["x"] == boxes["heading"]["x"], boxes
    assert boxes["visibility"]["y"] >= boxes["heading"]["bottom"], boxes


def test_a_locked_untitled_preview_draws_the_heading_card_for_its_rows(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """Locked, an empty heading card is not drawn, unless Layout 1 has
    help rows for it: then it holds them alone, starting at its top as
    the visibility card's title does, with the visibility card beside it."""
    session_id = new_session()
    _give_a_field_help_text(live_server.database_url, session_id)
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_card(page, session_id)
    expect(card).to_have_attribute("data-instrument-locked", "true")
    expect(
        card.locator("[data-new-model-band2-intro-card] .rs-help-row").first
    ).to_be_visible()
    boxes = _boxes(card)
    assert boxes["rowHome"] == "heading", boxes
    assert boxes["heading"]["y"] == boxes["visibility"]["y"], boxes
    assert boxes["heading"]["x"] < boxes["visibility"]["x"], boxes
    assert (
        boxes["row"]["y"] - boxes["heading"]["y"]
        == boxes["visibilityTitle"]["y"] - boxes["visibility"]["y"]
    ), boxes


def test_the_reviewer_surface_takes_the_instruments_layout(
    page: Page,
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    """The reviewer meets the same arrangement: Layout 1 by default, the
    help rows in the heading card, drawn for them alone on a lone
    untitled instrument and under the description once there is one."""
    session_id = new_session()
    seed_rosters(api, session_id)
    _give_a_field_help_text(live_server.database_url, session_id)
    activate(api, live_server.database_url, session_id)
    reviewer = page_as(REVIEWER_EMAIL)
    reviewer.goto(f"/me/sessions/{session_id}")
    intro = reviewer.locator(".rs-intro-columns").first
    expect(intro).to_have_attribute("data-intro-layout", "layout_1")
    boxes = intro.evaluate(_BOXES)
    assert boxes["rowHome"] == "heading", boxes
    assert boxes["heading"]["y"] == boxes["visibility"]["y"], boxes
    assert boxes["heading"]["x"] < boxes["visibility"]["x"], boxes

    _describe_instrument(live_server.database_url, session_id)
    reviewer.reload()
    intro = reviewer.locator(".rs-intro-columns").first
    boxes = intro.evaluate(_BOXES)
    title_bottom = intro.evaluate(
        "el => el.querySelector('.rs-intro-name h2').getBoundingClientRect().bottom"
    )
    assert boxes["rowHome"] == "heading", boxes
    assert boxes["row"]["y"] > title_bottom, boxes
    assert boxes["visibility"]["x"] > boxes["heading"]["x"], boxes


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


def _stray_gap(intro: Locator) -> float:
    """How far the intro's box runs below its lowest drawn card."""
    return intro.evaluate(
        """intro => {
          const bottoms = [...intro.querySelectorAll('.card')]
            .filter(el => el.offsetParent)
            .map(el => el.getBoundingClientRect().bottom);
          return intro.getBoundingClientRect().bottom - Math.max(...bottoms);
        }"""
    )


def test_narrow_with_no_help_row_leaves_no_stray_gap(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """The empty help column leaves the grid, so a one-column intro ends
    at its last card in either layout."""
    session_id = new_session()
    _hide_help_text(live_server.database_url, session_id)
    page.set_viewport_size({"width": 700, "height": 1000})
    card = open_unlocked(page, session_id)
    chip = card.locator("[data-intro-layout-chip]")
    intro = card.locator("[data-new-model-band2-intro-card]")
    for label in ("Layout 1", "Layout 2"):
        expect(chip).to_have_text(label)
        assert _stray_gap(intro) == 0, label
        chip.click()


def test_with_neither_heading_nor_help_row_visibility_keeps_the_left_half(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """A locked preview of a lone untitled instrument with no help text
    draws only the visibility card; Layout 1 leaves it on the left, with
    no gap below it."""
    session_id = new_session()
    _hide_help_text(live_server.database_url, session_id)
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_card(page, session_id)
    intro = card.locator("[data-new-model-band2-intro-card]")
    boxes = intro.evaluate(_BOXES)
    assert boxes["heading"] is None and boxes["help"] is None, boxes
    left = intro.evaluate("el => el.getBoundingClientRect().left")
    assert boxes["visibility"]["x"] == left, boxes
    assert _stray_gap(intro) == 0


def test_a_row_with_no_help_text_shows_only_while_unlocked(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """A field whose ≡ is on but whose help text is empty draws no row
    locked, as the reviewer surface draws none; unlocked its row is
    there to be typed into, the textarea named for its field."""
    session_id = new_session()
    _show_one_empty_help_text(live_server.database_url, session_id)
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_card(page, session_id)
    expect(card).to_have_attribute("data-instrument-locked", "true")
    assert _boxes(card)["rowCount"] == 0

    card.locator("[data-instrument-unlock-toggle]:visible").first.click()
    expect(card).to_have_attribute("data-instrument-locked", "false")
    textarea = card.locator(
        "[data-new-model-band2-intro-card] [data-help-card-textarea]"
    )
    expect(textarea).to_have_count(1)
    expect(textarea).to_have_attribute("aria-label", re.compile(r"^Help text for \S"))
