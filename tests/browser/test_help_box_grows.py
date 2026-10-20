"""A help text's edit box grows with its text (segment 19Y Item 5): an
unlocked instrument card's help box shows its whole text above a 60px
floor, follows the operator's typing, and re-fits when its width
changes; it takes no resize handle.
"""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Locator, Page, expect

from ._builder import open_unlocked
from .conftest import LiveServer
from .test_intro_layout_chip import _give_a_field_help_text

_BOX = "[data-new-model-band2-intro-card] [data-help-card-textarea]"
_LONG = "Score each teammate on what they contributed this term. " * 12


def _fit(box: Locator) -> dict:
    return box.evaluate(
        """el => ({height: el.getBoundingClientRect().height,
                   hidden: el.scrollHeight - el.clientHeight,
                   resize: getComputedStyle(el).resize})"""
    )


def test_a_long_help_text_shows_whole(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    _give_a_field_help_text(live_server.database_url, session_id, _LONG)
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    box = card.locator(_BOX).first
    expect(box).to_have_value(_LONG)
    fit = _fit(box)
    assert fit["height"] > 100 and fit["hidden"] <= 1, fit
    assert fit["resize"] == "none", fit


def test_a_short_help_text_keeps_the_floor_and_typing_grows_it(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    _give_a_field_help_text(live_server.database_url, session_id)
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    box = card.locator(_BOX).first
    expect(box).to_be_visible()
    assert abs(_fit(box)["height"] - 60) < 1

    box.fill(_LONG)
    fit = _fit(box)
    assert fit["height"] > 100 and fit["hidden"] <= 1, fit

    box.fill("Short again.")
    assert abs(_fit(box)["height"] - 60) < 1


def test_the_box_re_fits_when_its_width_changes(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """The layout chip moves the box into the other home, and a narrower
    window rewraps it; either way the whole text stays shown."""
    session_id = new_session()
    _give_a_field_help_text(live_server.database_url, session_id, _LONG)
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    wide = _fit(card.locator(_BOX).first)

    card.locator("[data-intro-layout-chip]").click()
    expect(card.locator("[data-intro-layout-chip]")).to_have_text("Layout 2")
    assert _fit(card.locator(_BOX).first)["hidden"] <= 1

    page.set_viewport_size({"width": 500, "height": 1000})
    box = card.locator(_BOX).first
    page.wait_for_function(
        """sel => { const el = document.querySelector(sel);
                    return el && el.scrollHeight - el.clientHeight <= 1; }""",
        arg=_BOX,
    )
    narrow = _fit(box)
    assert narrow["hidden"] <= 1, narrow
    assert narrow["height"] > wide["height"], (wide, narrow)
