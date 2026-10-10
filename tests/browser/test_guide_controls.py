"""The Guide's "Reading the controls" card (guide/ux_refinements.md Item 10):
every chip sample answers a click the way the chip it stands for does, the
row-switch sample R toggles like R on Instruments, and the delete guard's
button stays off until its box is ticked.
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
    # The row switch: a click flips it between Primary and Secondary.
    toggle = card.locator("[data-guide-toggle]")
    expect(toggle).to_have_attribute("aria-pressed", "true")
    on_bg = _bg(toggle)
    toggle.click()
    expect(toggle).to_have_attribute("aria-pressed", "false")
    expect(toggle).to_have_class("btn secondary")
    assert _bg(toggle) != on_bg
    toggle.click()
    expect(toggle).to_have_attribute("aria-pressed", "true")
    expect(toggle).to_have_class("btn")
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

    # Not chosen yet: amber until a click, then the options in turn and
    # back to unset, as the Instruments page's link chips cycle.
    unset = card.locator("[data-guide-unset-chip]")
    expect(unset).to_have_text("Not set")
    assert _bg(unset) == amber
    unset.click()
    expect(unset).to_have_text("All")
    assert _bg(unset) == dark
    unset.press("Enter")
    expect(unset).to_have_text("Filter using tags")
    unset.click()
    expect(unset).to_have_text("Not set")
    assert _bg(unset) == amber
    unset.press("Space")
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


def test_every_sample_has_a_tooltip(page: Page) -> None:
    """Each button, pill and chip sample, and the guard's box and button,
    says on hover what it is (the author, 2026-10-10)."""
    page.goto("/guide")
    samples = page.locator(
        "#guide-controls .guide-controls-table td:first-child > *,"
        " #guide-controls .guide-controls-demo input,"
        " #guide-controls .guide-controls-demo .pill,"
        " #guide-controls .guide-controls-demo button"
    )
    count = samples.count()
    assert count == 17
    for i in range(count):
        title = samples.nth(i).get_attribute("title")
        assert title and title.strip(), samples.nth(i).inner_text()
