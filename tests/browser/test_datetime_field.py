"""Session Home's date-time fields (segment 19X Item 6): a 24-hour text
box, a calendar button that opens the browser's picker, and a ✕ that
clears the box in one press.
"""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Page, expect


def test_the_box_takes_text_clears_in_one_press_and_saves(
    page: Page, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    page.goto(f"/operator/sessions/{session_id}?editing=1")
    end = page.locator("#mock-end")
    field = page.locator("[data-dt-field]", has=end)
    pick = field.locator("[data-dt-pick]")
    clear = field.locator("[data-dt-clear]")
    save = page.locator("[data-config-save]")
    # The script reveals both buttons; the native picker stays out of the
    # tab order and out of sight.
    expect(pick).to_be_visible()
    expect(clear).to_be_visible()
    expect(field.locator("[data-dt-picker]")).to_have_attribute("tabindex", "-1")
    expect(end).to_have_attribute("type", "text")

    # A pasted `T` form reads as the box's own 24-hour text.
    end.fill("2027-03-01T17:05")
    end.press("Tab")
    expect(end).to_have_value("2027-03-01 17:05")
    expect(save).to_be_enabled()

    with page.expect_navigation():
        save.click()
    page.wait_for_load_state("load")
    expect(end).to_have_value("2027-03-01 17:05")
    expect(save).to_be_disabled()

    # One press empties it, and counts as an edit.
    clear.click()
    expect(end).to_have_value("")
    expect(end).to_be_focused()
    expect(save).to_be_enabled()
    with page.expect_navigation():
        save.click()
    page.wait_for_load_state("load")
    expect(end).to_have_value("")


def test_the_buttons_hide_with_the_box_when_locked(
    page: Page, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    page.goto(f"/operator/sessions/{session_id}")
    card = page.locator("#session-config")
    expect(card).to_have_attribute("data-config-mode", "display")
    expect(page.locator("#mock-end")).to_be_hidden()
    expect(page.locator("[data-dt-clear]").first).to_be_hidden()
    expect(page.locator("[data-dt-pick]").first).to_be_hidden()
