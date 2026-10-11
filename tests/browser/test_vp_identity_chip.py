"""The Band 2 card's reviewer-identity chip, live.

ProfileLink updates Item 2 (``guide/profilelink_updates.md``): beside a
Raw Reviewees or Observers Responses released cell, the chip cycles
``Name only`` / ``Name, email`` (and ``Name, email, profile`` once some
reviewer has a ProfileLink) by click or by Enter and Space, repaints the
locked table's pill, and the card's Save stores it. The mode chips
take Enter and Space too.
"""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Locator, Page, expect

from ._builder import open_unlocked, save, save_button


def _cycle(card: Locator, audience: str) -> Locator:
    return card.locator(
        f'[data-new-model-vp-cycle-audience="{audience}"]'
        '[data-new-model-vp-cycle-window="after_release"]'
    )


def test_enter_and_space_cycle_a_mode_chip(
    page: Page, new_session: Callable[[], int]
) -> None:
    """A keyboard user reaches Raw, and so the identity chip, without a
    mouse (the author, 2026-10-11)."""
    card = open_unlocked(page, new_session())
    cycle = _cycle(card, "reviewee")
    expect(cycle).to_have_text("—")
    expect(save_button(card)).to_be_disabled()
    cycle.focus()
    page.keyboard.press("Enter")  # — → Raw
    expect(cycle).to_have_attribute("data-new-model-vp-current-slug", "raw")
    # The keyed cycle marks the card dirty, as a click does.
    expect(save_button(card)).to_be_enabled()
    chip = card.locator('[data-new-model-vp-identity="reviewee"]')
    expect(chip).to_be_visible()
    page.keyboard.press("Space")  # Raw → Anonymized
    expect(cycle).to_have_attribute(
        "data-new-model-vp-current-slug", "anonymized"
    )
    expect(chip).to_be_hidden()
    # The keyed cycle wrote the hidden input Save sends.
    expect(
        card.locator('[data-new-model-vp-input="reviewee-after_release"]')
    ).to_have_value("anonymized")


def test_the_identity_chip_follows_its_cell_and_cycles(
    page: Page, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    card = open_unlocked(page, session_id)
    for audience in ("reviewee", "observer"):
        cycle = _cycle(card, audience)
        chip = card.locator(f'[data-new-model-vp-identity="{audience}"]')
        expect(cycle).to_have_text("—")
        expect(chip).to_be_hidden()
        cycle.click()  # — → Raw
        expect(cycle).to_have_attribute("data-new-model-vp-current-slug", "raw")
        expect(chip).to_be_visible()
        expect(chip).to_have_text("Name, email")
        # No reviewer has a link: the cycle is the first two levels.
        chip.click()
        expect(chip).to_have_text("Name only")
        chip.focus()
        page.keyboard.press("Enter")
        expect(chip).to_have_text("Name, email")
        page.keyboard.press("Space")
        expect(chip).to_have_text("Name only")
        if audience == "reviewee":
            locked = card.locator('[data-new-model-vp-identity-preview="reviewee"]')
            expect(locked).to_have_text("Name only")
        cycle.click()  # Raw → Anonymized
        expect(chip).to_be_hidden()
        cycle.click()  # Anonymized → Summarized
        cycle.click()  # Summarized → —
        cycle.click()  # — → Raw: the level it held comes back
        expect(chip).to_have_text("Name only")

    save(page, card)
    page.reload()
    card = open_unlocked(page, session_id)
    for audience in ("reviewee", "observer"):
        expect(card.locator(f'[data-new-model-vp-identity="{audience}"]')).to_have_text(
            "Name only"
        )
