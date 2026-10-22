"""The Band 2 preview's String answer box takes no resize handle
(segment 19Y Item 4): a drag in the preview would persist nowhere. The
reviewer surface's boxes now fit their text and take none either
(19X Item 10, `test_answer_box_fits.py`).
"""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Page, expect

from ._builder import open_card, open_unlocked

_PREVIEW_BOX = "[data-new-model-band2] textarea[disabled][aria-hidden='true']"


def _resize(box) -> str:
    return box.evaluate("el => getComputedStyle(el).resize")


def test_the_preview_box_has_no_handle_locked_or_unlocked(
    page: Page, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    card = open_card(page, session_id)
    box = card.locator(_PREVIEW_BOX).first
    expect(box).to_be_visible()
    assert _resize(box) == "none"

    card = open_unlocked(page, session_id)
    box = card.locator(_PREVIEW_BOX).first
    expect(box).to_be_visible()
    assert _resize(box) == "none"
