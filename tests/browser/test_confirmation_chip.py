"""The Email Template page's response-confirmation chip (guide/ux_refinements.md
Item 9): a cycle chip under the "Responses received email" heading, always
dark, reading "Send response confirmation" or "Don't send response
confirmation", saved with the composer.
"""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Page, expect

from .conftest import app_url


def test_the_confirmation_chip_cycles_and_saves(
    page: Page, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    page.goto(app_url(f"/operator/sessions/{session_id}/setup-invite?template=responses_received"))
    chip = page.locator("[data-send-confirmation-chip]")
    expect(chip).to_have_text("Send response confirmation")
    dark = chip.evaluate("el => getComputedStyle(el).backgroundColor")
    save = page.locator("#setupinvite-save-button")
    expect(save).to_be_disabled()

    chip.click()
    expect(chip).to_have_text("Don't send response confirmation")
    assert chip.evaluate("el => getComputedStyle(el).backgroundColor") == dark
    expect(save).to_be_enabled()
    with page.expect_navigation():
        save.click()

    chip = page.locator("[data-send-confirmation-chip]")
    expect(chip).to_have_text("Don't send response confirmation")
    expect(chip.locator("input")).not_to_be_checked()
