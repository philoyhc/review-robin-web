"""The Band 2 card's reviewer-identity chip, live.

ProfileLink updates Item 2 (``guide/profilelink_updates.md``): beside a
Raw Reviewees or Observers Responses released cell, the chip cycles
``Reviewer name only`` / ``Reviewer name, email`` (and ``Reviewer name,
email, profile`` once some reviewer has a ProfileLink) by click or by
Enter and Space, repaints the locked table's pill, and the card's Save
stores it. The mode chips take Enter and Space too.
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
    page: Page, new_session: Callable[[], str]
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
    page: Page, new_session: Callable[[], str]
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
        expect(chip).to_have_text("Reviewer name, email")
        # No reviewer has a link: the cycle is the first two levels.
        chip.click()
        expect(chip).to_have_text("Reviewer name only")
        chip.focus()
        page.keyboard.press("Enter")
        expect(chip).to_have_text("Reviewer name, email")
        page.keyboard.press("Space")
        expect(chip).to_have_text("Reviewer name only")
        if audience == "reviewee":
            locked = card.locator('[data-new-model-vp-identity-preview="reviewee"]')
            expect(locked).to_have_text("Reviewer name only")
        cycle.click()  # Raw → Anonymized
        expect(chip).to_be_hidden()
        cycle.click()  # Anonymized → Summarized
        cycle.click()  # Summarized → —
        cycle.click()  # — → Raw: the level it held comes back
        expect(chip).to_have_text("Reviewer name only")

    save(page, card)
    page.reload()
    card = open_unlocked(page, session_id)
    for audience in ("reviewee", "observer"):
        expect(card.locator(f'[data-new-model-vp-identity="{audience}"]')).to_have_text(
            "Reviewer name only"
        )


def _widths(card: Locator) -> list[float]:
    """The editor table's three header widths, in px."""
    return card.locator("[data-new-model-vp-editor] table.vp-grid th").evaluate_all(
        "ths => ths.map(th => th.getBoundingClientRect().width)"
    )


def test_the_released_column_widens_while_an_identity_pill_shows(
    page: Page, new_session: Callable[[], str]
) -> None:
    """The author, 2026-10-11: the second pill crowded the column. A
    visible identity pill widens Responses released; hiding it again
    restores the even windows, live, as the chip cycles."""
    card = open_unlocked(page, new_session())
    audience, ongoing, released = _widths(card)
    assert abs(ongoing - released) < 2
    cycle = _cycle(card, "reviewee")
    cycle.click()  # — → Raw: the identity pill shows
    expect(card.locator('[data-new-model-vp-identity="reviewee"]')).to_be_visible()
    audience_wide, ongoing_wide, released_wide = _widths(card)
    assert released_wide > ongoing_wide + 50
    assert released_wide > released + 50
    assert audience_wide < audience - 20  # 28% → 20%
    cycle.click()  # Raw → Anonymized: hidden again
    expect(card.locator('[data-new-model-vp-identity="reviewee"]')).to_be_hidden()
    audience_back, ongoing_back, released_back = _widths(card)
    assert abs(ongoing_back - released_back) < 2
    assert abs(audience_back - audience) < 2
