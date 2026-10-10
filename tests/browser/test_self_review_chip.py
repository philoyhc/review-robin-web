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


def test_switching_link_3_to_group_turns_the_chip_back_to_include(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    """The Individual → Group move clears the exclusion (19O Item 2) and
    renames the chip with it; the line takes the group sentence. Link 3
    needs a reviewee tag to group by."""
    session_id = new_session()
    for kind, body in (
        ("reviewers", b"ReviewerName,ReviewerEmail\nRana,rana@example.edu\n"),
        ("reviewees", b"RevieweeName,RevieweeEmail,RevieweeTag1\nCarol,carol@example.edu,Blue\n"),
    ):
        response = api.post(
            f"/operator/sessions/{session_id}/{kind}/import",
            files={"file": (f"{kind}.csv", body, "text/csv")},
            follow_redirects=False,
        )
        assert response.status_code in (200, 303), response.text
    pin_full_matrix(live_server.database_url, session_id)
    card = open_unlocked(page, session_id)
    chip = card.locator("[data-new-model-self-review-chip]")
    chip.click()
    expect(chip).to_have_text("Exclude self reviews")

    link3 = card.locator("[data-new-model-unit-mode][role=button]")
    link3.click()
    expect(link3).to_have_attribute(
        "data-new-model-unit-mode", "group"
    )
    expect(chip).to_have_text("Include self reviews")
    expect(chip.locator("input")).not_to_be_checked()
    expect(card.locator("[data-new-model-self-review-copy]")).to_have_text(
        "A self review is where the reviewer is in the group being reviewed"
    )

