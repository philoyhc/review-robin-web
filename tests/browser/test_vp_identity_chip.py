"""The Band 2 card's reviewer-identity pill follows its Raw cell live.

ProfileLink updates Item 2 rung 1 (``guide/profilelink_updates.md``):
cycling the Reviewees or Observers Responses released cell to Raw shows
the inert "Name, email" pill beside it, and the Reviewees one in the
card's locked table too; cycling on hides them again. The pill is not
a control yet, so a click on it changes nothing.
"""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Locator, Page, expect

from ._builder import open_unlocked


def _cycle(card: Locator, audience: str) -> Locator:
    return card.locator(
        f'[data-new-model-vp-cycle-audience="{audience}"]'
        '[data-new-model-vp-cycle-window="after_release"]'
    )


def test_the_identity_pill_follows_a_raw_released_cell(
    page: Page, new_session: Callable[[], int]
) -> None:
    card = open_unlocked(page, new_session())
    for audience in ("reviewee", "observer"):
        cycle = _cycle(card, audience)
        pill = card.locator(f'[data-new-model-vp-identity="{audience}"]')
        expect(cycle).to_have_text("—")
        expect(pill).to_be_hidden()
        cycle.click()  # — → Raw
        expect(cycle).to_have_attribute("data-new-model-vp-current-slug", "raw")
        expect(pill).to_be_visible()
        expect(pill).to_have_text("Name, email")
        pill.click()  # inert: nothing moves
        expect(pill).to_have_text("Name, email")
        expect(cycle).to_have_attribute("data-new-model-vp-current-slug", "raw")
        if audience == "reviewee":
            locked = card.locator('[data-new-model-vp-identity-preview="reviewee"]')
            assert locked.get_attribute("hidden") is None
        cycle.click()  # Raw → Anonymized
        expect(pill).to_be_hidden()
        if audience == "reviewee":
            assert locked.get_attribute("hidden") is not None
