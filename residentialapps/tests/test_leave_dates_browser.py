"""Apply's live check of the dates (author, 2026-11-09), in a real
Chromium: keying in dates fills Days of leave and its message from the
server's check, and Submit opens only once they pass. Served as the sort
tests are; without a Chromium build the test skips, saying why, and
`RRW_REQUIRE_BROWSER=1` fails it."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from residentialapps.tests.test_sort_persistence_browser import (  # noqa: F401  (the fixture)
    ORIGIN,
    page,
)


def test_keyed_in_dates_are_checked_and_open_submit(page: Page) -> None:  # noqa: F811
    # At the default, By invitation, Chloe Lim is not invited: more than her
    # balance is refused.
    page.goto(ORIGIN + "/ra-leave/apply")
    submit = page.locator("#send")
    expect(submit).to_be_disabled()
    page.fill("#first", "2026-11-30")
    page.fill("#last", "2026-11-29")
    page.locator("#last").dispatch_event("change")
    expect(page.locator("#days-note")).to_have_text("The last day is before the first day.")
    expect(submit).to_be_disabled()
    page.fill("#last", "2026-12-04")
    page.locator("#last").dispatch_event("change")
    expect(page.locator("#days")).to_have_text("5 days")
    expect(page.locator("#days-note")).to_have_text(
        "3 days more than your Personal leave (2 available): shorten it."
    )
    page.fill("#last", "2026-12-01")
    page.locator("#last").dispatch_event("change")
    expect(page.locator("#days")).to_have_text("2 days")
    expect(page.locator("#days-note")).to_have_text("")
    expect(submit).to_be_enabled()
