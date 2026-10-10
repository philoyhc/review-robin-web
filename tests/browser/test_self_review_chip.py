"""The Instruments card's self-review chip (guide/ux_refinements.md Item 8):
a cycle chip, always dark, reading "Include self reviews" or "Exclude self
reviews", with the line under it saying what a self review is.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Page, expect

from ._builder import open_card, open_unlocked, pin_full_matrix, save
from .conftest import LiveServer


def test_the_self_review_chip_cycles_and_saves(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    pin_full_matrix(live_server.database_url, session_id)
    card = open_unlocked(page, session_id)
    chip = card.locator("[data-new-model-self-review-chip]")
    expect(chip).to_be_visible()
    expect(chip).to_have_text("Include self reviews")
    expect(card.locator("[data-new-model-self-review-copy]")).to_have_text(
        "A self review is where the individual reviewed is the reviewer"
    )
    dark = chip.evaluate("el => getComputedStyle(el).backgroundColor")

    chip.click()
    expect(chip).to_have_text("Exclude self reviews")
    assert chip.evaluate("el => getComputedStyle(el).backgroundColor") == dark
    save(page, card)

    card = open_unlocked(page, session_id)
    chip = card.locator("[data-new-model-self-review-chip]")
    expect(chip).to_have_text("Exclude self reviews")
    expect(chip.locator('input[name="exclude_self_reviews"]')).to_be_checked()


def test_a_locked_cards_self_review_chip_is_a_plain_unfaded_pill(
    page: Page, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    """On a locked card the chip reads as a display pill, as Band 3's do,
    but "Include self reviews" is a state, not an off switch, so it is
    not faded (ux_refinements Item 8)."""
    session_id = new_session()
    pin_full_matrix(live_server.database_url, session_id)
    card = open_card(page, session_id)
    expect(card).to_have_attribute("data-instrument-locked", "true")
    chip = card.locator("[data-new-model-self-review-chip]")
    expect(chip).to_have_text("Include self reviews")
    assert chip.evaluate("el => getComputedStyle(el).opacity") == "1"

