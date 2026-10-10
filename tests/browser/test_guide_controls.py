"""The Guide's "Reading the controls" card (guide/ux_refinements.md Item 10):
every chip sample answers a click the way the chip it stands for does, and
the delete guard's button stays off until its box is ticked.
"""

from __future__ import annotations

from playwright.sync_api import Locator, Page, expect


def _bg(locator: Locator) -> str:
    return locator.evaluate("el => getComputedStyle(el).backgroundColor")


def test_the_chip_samples_answer_a_click(page: Page) -> None:
    page.goto("/guide")
    card = page.locator("#guide-controls")
    email = card.locator("label.tag-chip", has_text="Email")
    tag = card.locator("label.tag-chip", has_text="Tag1")
    dark = _bg(email)
    light = _bg(tag)
    assert dark != light

    # On/off: the fill follows the box.
    tag.click()
    assert _bg(tag) == dark
    email.click()
    assert _bg(email) == light

    # Some of a set: amber, then all on, then none.
    partial = card.locator("[data-guide-partial-chip]")
    expect(partial).to_have_text("Include 1 self review")
    amber = _bg(partial)
    assert amber not in (dark, light)
    partial.click()
    expect(partial).to_have_text("Include 2 self reviews")
    assert _bg(partial) == dark
    partial.click()
    expect(partial).to_have_text("Include 0 self reviews")
    assert _bg(partial) == light

    # A choice between named options: the label moves, the fill stays dark.
    cycle = card.locator("[data-guide-cycle-chip]")
    expect(cycle).to_have_text("Include self reviews")
    cycle.click()
    expect(cycle).to_have_text("Exclude self reviews")
    assert _bg(cycle) == dark
    cycle.click()
    expect(cycle).to_have_text("Include self reviews")

    # Not chosen yet: amber until a click, then the options in turn.
    unset = card.locator("[data-guide-unset-chip]")
    expect(unset).to_have_text("Not set")
    assert _bg(unset) == amber
    unset.click()
    expect(unset).to_have_text("All")
    assert _bg(unset) == dark
    unset.press("Enter")
    expect(unset).to_have_text("Filter by Tag1")
    unset.click()
    expect(unset).to_have_text("All")

    # Held where it is: dark, and a click changes nothing.
    fixed = card.locator("label.tag-chip.is-fixed")
    assert _bg(fixed) == dark
    fixed.click(force=True)
    expect(fixed.locator("input")).to_be_checked()


def test_the_delete_guard_turns_its_button_on(page: Page) -> None:
    page.goto("/guide")
    card = page.locator("#guide-controls")
    button = card.locator('[data-delete-btn="guide-demo"]')
    expect(button).to_be_disabled()
    card.locator('[data-delete-confirm="guide-demo"]').check()
    expect(button).to_be_enabled()
    card.locator('[data-delete-confirm="guide-demo"]').uncheck()
    expect(button).to_be_disabled()
