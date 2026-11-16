"""A linked instrument's fixed structure looks fixed (segment 23F rung 7h,
author 2026-11-16): Band 1's chips carry the lock glyph, and the response
fields' buttons and boxes take the inactive look, where a native card's
stay live."""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Locator, Page

from ._builder import open_unlocked
from .conftest import LiveServer
from .test_linked_help_text import _link

_CHIP = "[data-new-model-rule-mode]"
_BUTTON = "[data-new-model-rf-row] [data-new-model-rf-required]"


def _glyph(chip: Locator) -> str:
    return chip.evaluate("el => getComputedStyle(el, '::before').content")


def _opacity(element: Locator) -> float:
    return float(element.evaluate("el => getComputedStyle(el).opacity"))


def test_a_linked_cards_structure_looks_fixed(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    _link(live_server.database_url, session_id)
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    assert _glyph(card.locator(_CHIP).first) == '""'
    assert _opacity(card.locator(_BUTTON).first) == 0.5


def test_a_native_cards_structure_stays_live(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    assert _glyph(card.locator(_CHIP).first) == "none"
    assert _opacity(card.locator(_BUTTON).first) == 1.0
