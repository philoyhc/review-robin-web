"""Session Home's details card: Save only saves, and keeps the seat.

19U Item 4 (author, 2026-10-08). Save used to lock the card and reload
to ``#session-config``, which scrolled the card's top edge into view —
from the Save button at its foot, a jump. Now Save comes back with the
card still unlocked, at the scroll position it left, with no fragment
in the URL; only Lock locks.
"""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Page, expect


def test_save_keeps_the_card_unlocked_and_the_scroll(
    page: Page, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    # Short enough that the Save button sits below the fold.
    page.set_viewport_size({"width": 1280, "height": 500})
    page.goto(f"/operator/sessions/{session_id}?editing=1")
    card = page.locator("#session-config")
    expect(card).to_have_attribute("data-config-mode", "edit")

    page.locator("#mock-description").fill("Saved without a jump")
    save = page.locator("[data-config-save]")
    save.scroll_into_view_if_needed()
    seat = page.evaluate("window.scrollY")
    assert seat > 0, "the page did not scroll; the test proves nothing"

    with page.expect_navigation():
        save.click()
    page.wait_for_load_state("load")

    assert page.url.endswith(f"/operator/sessions/{session_id}?editing=1")
    assert "#" not in page.url
    expect(card).to_have_attribute("data-config-mode", "edit")
    expect(page.locator("#mock-description")).to_have_value("Saved without a jump")
    # A clean card after the save: nothing to save or cancel yet.
    expect(save).to_be_disabled()
    assert abs(page.evaluate("window.scrollY") - seat) <= 2

    # Lock locks, in place, and drops the param so a reload stays locked.
    page.locator("[data-config-lock-toggle]").click()
    expect(card).to_have_attribute("data-config-mode", "display")
    assert "editing" not in page.url
    page.reload()
    expect(card).to_have_attribute("data-config-mode", "display")
