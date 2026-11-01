"""Sys Admin → Accounts: the invite box's directory picker (segment 19Z,
invite from the directory, rung 19). The live server runs with fake auth,
so the search asks the fake directory: typing a name offers its people as
"Name <address>", and picking one puts the address in the box."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from .conftest import app_url

ACCOUNTS = "/operator/sys-admin/users"


def test_a_name_offers_the_directory_s_people(page: Page) -> None:
    page.goto(app_url(ACCOUNTS))
    box = page.locator("#invite-email")
    options = page.locator("#invite-directory-options option")

    box.press_sequentially("Jane")
    expect(options).to_have_count(1)
    expect(options.first).to_have_attribute("value", "jane.tan@example.edu")
    expect(options.first).to_have_attribute("label", "Jane Tan <jane.tan@example.edu>")
    expect(page.locator("[data-directory-status]")).to_be_hidden()

    # A pick puts the address in the box, and the offer stands.
    box.fill("jane.tan@example.edu")
    page.wait_for_timeout(500)
    expect(options).to_have_count(1)
    expect(page.locator("[data-invite-submit]")).to_be_enabled()


def test_too_short_offers_nothing_and_no_match_says_so(page: Page) -> None:
    page.goto(app_url(ACCOUNTS))
    box = page.locator("#invite-email")
    status = page.locator("[data-directory-status]")

    box.press_sequentially("zzzq")
    expect(status).to_have_text("No one in the directory matches that.")
    expect(page.locator("#invite-directory-options option")).to_have_count(0)

    box.fill("ja")
    box.dispatch_event("input")
    expect(status).to_be_hidden()

    box.fill("Arun")
    box.dispatch_event("input")
    expect(page.locator("#invite-directory-options option")).to_have_count(1)
    page.click("[data-invite-cancel]")
    expect(page.locator("#invite-directory-options option")).to_have_count(0)
