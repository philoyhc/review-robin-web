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
    # Her sign-in name differs from her mail, so the label keeps it.
    expect(options.first).to_have_attribute(
        "label", "Jane Tan <jane.tan@example.edu> · e0123456@example.edu"
    )
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


def test_an_answer_for_old_text_is_dropped(page: Page) -> None:
    """A slow answer arriving after the box was shortened fills nothing."""
    page.goto(app_url(ACCOUNTS))
    release: list = []
    page.route("**/directory-search*", lambda route: release.append(route))
    box = page.locator("#invite-email")
    box.press_sequentially("Jane")
    page.wait_for_timeout(500)
    assert release, "the search was asked"
    box.fill("ja")
    box.dispatch_event("input")
    page.wait_for_timeout(400)
    release[0].continue_()
    page.wait_for_timeout(500)
    expect(page.locator("#invite-directory-options option")).to_have_count(0)
    expect(page.locator("[data-directory-status]")).to_be_hidden()


def test_a_sign_in_name_search_keeps_its_match_in_the_label(page: Page) -> None:
    page.goto(app_url(ACCOUNTS))
    page.locator("#invite-email").press_sequentially("e0123")
    option = page.locator("#invite-directory-options option")
    expect(option).to_have_count(1)
    assert "e0123456@example.edu" in (option.first.get_attribute("label") or "")

    # Arun's sign-in name is his mail: nothing added.
    page.locator("#invite-email").fill("Arun")
    page.locator("#invite-email").dispatch_event("input")
    expect(option.first).to_have_attribute("label", "Arun Kumar <arun.kumar@example.edu>")
