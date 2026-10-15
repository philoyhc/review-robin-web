"""The error page's way out, driven in a browser (participant audit P2,
`guide/participant_surface_check.md`). "Go back" shows only when the
page was reached from a page of the app, and links straight to it; with
no such referrer the page offers only its own link."""

from __future__ import annotations

from playwright.sync_api import Page, expect

MISSING = "/operator/no/such/page"


def test_a_direct_visit_offers_only_the_pages_own_link(page: Page) -> None:
    page.goto(MISSING)
    expect(page.locator("[data-error-home]")).to_be_visible()
    expect(page.locator("[data-error-home]")).to_have_attribute(
        "href", "/operator/sessions"
    )
    expect(page.locator("[data-error-history]")).to_be_hidden()


def test_arriving_from_an_app_page_offers_go_back_to_it(page: Page) -> None:
    page.goto("/about")
    page.evaluate(f"window.location.href = {MISSING!r}")
    page.wait_for_url(f"**{MISSING}")
    back = page.locator("[data-error-history]")
    expect(back).to_be_visible()
    assert back.get_attribute("href").endswith("/about")
    with page.expect_navigation():
        back.click()
    assert page.url.endswith("/about")
