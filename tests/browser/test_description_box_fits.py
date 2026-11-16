"""The instrument description's edit box fits its text (author,
2026-11-16), as the answer boxes do: no drag handle, two lines empty,
and it grows with what is typed."""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Locator, Page

from ._builder import open_unlocked
from .conftest import LiveServer

_BOX = "[data-intro-description-input]"
_LONG = "Score each teammate on what they contributed this term. " * 12


def _fit(box: Locator) -> dict[str, float | str]:
    return box.evaluate(
        """el => ({height: el.getBoundingClientRect().height,
                   hidden: el.scrollHeight - el.clientHeight,
                   resize: getComputedStyle(el).resize})"""
    )


def test_the_description_box_grows_with_its_text(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    box = card.locator(_BOX)
    box.fill("")
    empty = _fit(box)
    assert empty["resize"] == "none", empty
    assert float(empty["height"]) < 70, empty  # two lines, not the old 6.5em

    box.fill(_LONG)
    full = _fit(box)
    assert float(full["height"]) > float(empty["height"]) + 40, full
    assert float(full["hidden"]) <= 1, full
