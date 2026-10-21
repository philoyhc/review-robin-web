"""Band 2's heading follows the instrument's name as it is typed in
Band 1 (segment 19Y Item 6), by the rule Lock applies, while the card
stays unsaved.
"""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Page, expect

from ._builder import open_unlocked

_HEADING = "[data-new-model-band2-intro-card] [data-intro-title-view]"


def test_typing_a_name_updates_the_heading_unsaved(
    page: Page, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    card = open_unlocked(page, session_id)
    name = card.locator("[data-card-title-input]")
    heading = card.locator(_HEADING)

    name.fill("Peer Review")
    expect(heading).to_have_text("Peer Review")
    expect(heading).to_be_visible()
    expect(card).to_have_attribute("data-instrument-dirty", "true")

    name.fill("Team Peer Review")
    expect(heading).to_have_text("Team Peer Review")

    # Cleared, a lone instrument with no description draws no heading.
    card.locator("[data-intro-description-input]").fill("")
    name.fill("")
    expect(heading).to_be_hidden()
