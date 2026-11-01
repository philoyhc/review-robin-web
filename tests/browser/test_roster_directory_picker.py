"""The roster rows' directory picker (segment 19Z, invite from the
directory, rung 20), in Chromium against the fake directory: either box
searches; picking a name fills its address, picking an address fills its
name, and both stay editable."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from playwright.sync_api import Page, expect

from .conftest import app_url


@pytest.mark.parametrize(
    ("roster", "name_box", "address_box"),
    [
        ("reviewers", 'input[name="name"]', 'input[name="email"]'),
        ("reviewees", 'input[name="name"]', 'input[name="email_or_identifier"]'),
    ],
)
def test_a_picked_name_fills_its_address(
    page: Page, new_session: Callable[[], str], roster: str, name_box: str, address_box: str
) -> None:
    page.goto(app_url(f"/operator/sessions/{new_session()}/{roster}?add=1"))
    name = page.locator(f"tr {name_box}[data-directory-field]")
    address = page.locator(f"tr {address_box}[data-directory-field]")

    name.press_sequentially("Jane")
    options = page.locator("#directory-name-options option")
    expect(options).to_have_count(1)
    expect(options.first).to_have_attribute("value", "Jane Tan")
    expect(options.first).to_have_attribute("label", "jane.tan@example.edu")

    name.fill("Jane Tan")
    name.dispatch_event("input")
    expect(address).to_have_value("jane.tan@example.edu")
    # Still editable: the operator's own spelling stands.
    name.fill("Jane T.")
    expect(address).to_have_value("jane.tan@example.edu")


def test_a_picked_address_fills_its_name_and_a_sign_in_name_finds_it(
    page: Page, new_session: Callable[[], str]
) -> None:
    page.goto(app_url(f"/operator/sessions/{new_session()}/reviewers?add=1"))
    name = page.locator('tr input[name="name"][data-directory-field]')
    address = page.locator('tr input[name="email"][data-directory-field]')

    address.press_sequentially("e0123")
    options = page.locator("#directory-address-options option")
    expect(options).to_have_count(1)
    expect(options.first).to_have_attribute("value", "jane.tan@example.edu")
    expect(options.first).to_have_attribute("label", "Jane Tan · e0123456@example.edu")

    address.fill("jane.tan@example.edu")
    address.dispatch_event("input")
    expect(name).to_have_value("Jane Tan")


def test_no_match_says_so_under_the_box(page: Page, new_session: Callable[[], str]) -> None:
    page.goto(app_url(f"/operator/sessions/{new_session()}/reviewers?add=1"))
    page.locator('tr input[name="name"][data-directory-field]').press_sequentially("zzzq")
    expect(page.locator("tr [data-directory-status]").first).to_have_text(
        "No one in the directory matches that."
    )


def test_a_help_contact_pick_fills_name_and_address(page: Page) -> None:
    """Rung 21: one box, filled with "Name <address>", the form the
    placeholder shows and `$help_contact` reads best in."""
    page.goto(app_url("/operator/sessions/new"))
    box = page.locator("#help_contact")
    box.press_sequentially("Jane")
    options = page.locator("#directory-contact-options option")
    expect(options).to_have_count(1)
    expect(options.first).to_have_attribute("value", "Jane Tan <jane.tan@example.edu>")
    expect(options.first).to_have_attribute("label", "e0123456@example.edu")
    box.fill("Jane Tan <jane.tan@example.edu>")
    box.dispatch_event("input")
    page.wait_for_timeout(500)
    expect(box).to_have_value("Jane Tan <jane.tan@example.edu>")
    expect(page.locator("[data-directory-group] [data-directory-status]")).to_be_hidden()


def test_a_pick_never_overwrites_an_address_already_there(
    page: Page, new_session: Callable[[], str]
) -> None:
    """An edit row's own address (or a reviewee's identifier) stays when a
    name is picked; one the picker filled itself is replaced."""
    page.goto(app_url(f"/operator/sessions/{new_session()}/reviewees?add=1"))
    name = page.locator('tr input[name="name"][data-directory-field]')
    address = page.locator('tr input[name="email_or_identifier"][data-directory-field]')
    address.fill("ANON-042")

    name.press_sequentially("Jane")
    expect(page.locator("#directory-name-options option")).to_have_count(1)
    name.fill("Jane Tan")
    name.dispatch_event("input")
    expect(address).to_have_value("ANON-042")

    # Cleared, a pick fills it; a second pick replaces the picker's own fill.
    address.fill("")
    name.dispatch_event("input")
    expect(address).to_have_value("jane.tan@example.edu")
    name.fill("Arun")
    name.dispatch_event("input")
    expect(page.locator("#directory-name-options option").first).to_have_attribute("value", "Arun Kumar")
    name.fill("Arun Kumar")
    name.dispatch_event("input")
    expect(address).to_have_value("arun.kumar@example.edu")
