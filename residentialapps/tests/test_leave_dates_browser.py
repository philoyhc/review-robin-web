"""Apply's live check of the dates (author, 2026-11-09), in a real
Chromium: keying in dates fills Days of leave and its message from the
server's check, and Submit opens only once they pass. And Leave records'
period, applied on choosing it (author, 2026-11-10). Served as the sort
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


def test_leave_records_apply_a_period_on_choosing_it_and_stay_at_the_top(
    page: Page,  # noqa: F811
) -> None:
    """Author, 2026-11-10: no Show period button; choosing a period reloads
    with it, the chips' state kept, at the top of the page, as a chip does."""
    page.set_viewport_size({"width": 1366, "height": 600})
    page.goto(ORIGIN + "/ra-leave/staff/records?as=Sam%20Lee&hide=Rejected")
    expect(page.locator("#period-form button")).to_have_count(0)  # noscript only
    page.evaluate("window.scrollTo(0, 300)")
    with page.expect_navigation():
        page.select_option("#period", "whole")
    assert "period=whole" in page.url and "Rejected" in page.url
    assert page.evaluate("window.scrollY") == 0
    expect(page.locator("#period")).to_have_value("whole")
    page.locator("#rec-filters > summary").click()  # Filters starts closed
    page.evaluate("window.scrollTo(0, 300)")
    with page.expect_navigation():
        page.locator(".rec-filters").nth(2).locator("a", has_text="Clear all").click()  # Precinct
    assert page.evaluate("window.scrollY") == 0
    assert "period=whole" in page.url


def test_leave_records_wait_for_a_forward_range(page: Page) -> None:  # noqa: F811
    """Codex, 2026-11-10: a From moved past To waits for To instead of
    submitting a backwards range; a forward one applies."""
    page.goto(ORIGIN + "/ra-leave/staff/records?as=Sam%20Lee")
    page.fill("#from", "2026-12-01")
    page.locator("#from").dispatch_event("change")
    page.wait_for_timeout(300)
    assert "period=custom" not in page.url  # no reload: To still 3 Nov
    with page.expect_navigation():
        page.fill("#to", "2026-12-31")
        page.locator("#to").dispatch_event("change")
    assert "from=2026-12-01" in page.url and "to=2026-12-31" in page.url


def test_leave_records_filters_start_closed_and_columns_hide_and_stay(
    page: Page,  # noqa: F811
) -> None:
    """Author, 2026-11-10: the chips sit in a Filters expander, closed
    until opened, its summary naming what is off; a column chip hides its
    column at once, and the browser keeps both choices."""
    page.goto(ORIGIN + "/ra-leave/admin/records?hide=Rejected")
    assert not page.evaluate("document.getElementById('rec-filters').open")
    expect(page.locator("#rec-off")).to_have_text(" · 1 off: Rejected")
    page.locator("#rec-filters > summary").click()
    page.locator('[data-col-toggle="submitted"]').click()
    expect(page.locator("#rec-off")).to_have_text(" · 2 off: Rejected; column Submitted")
    expect(page.locator('#rec-table th[data-col="submitted"]')).to_be_hidden()
    page.reload()
    assert not page.evaluate("document.getElementById('rec-filters').open")  # starts closed
    expect(page.locator('#rec-table th[data-col="submitted"]')).to_be_hidden()
    page.locator("#rec-filters > summary").click()
    page.locator('[data-cols-all="false"]').click()
    expect(page.locator('#rec-table th[data-col="precinct"]')).to_be_hidden()
    page.locator('[data-cols-all="true"]').click()
    expect(page.locator('#rec-table th[data-col="submitted"]')).to_be_visible()


def test_leave_records_keep_the_period_and_chips_in_the_browser(
    page: Page,  # noqa: F811
) -> None:
    """Author, 2026-11-10: the selectors are kept in the browser. Only a
    choice made on the page is kept, per viewer; a visit naming no filter
    takes it back; a link naming its own (a tile, a back link) is shown as
    it is and does not overwrite it (the cold read)."""
    page.goto(ORIGIN + "/ra-leave/staff/records?as=Sam%20Lee")
    with page.expect_navigation():
        page.select_option("#period", "term")
    page.locator("#rec-filters > summary").click()
    with page.expect_navigation():
        page.locator(".rec-filters").first.locator("a", has_text="Rejected").click()
    page.goto(ORIGIN + "/ra-leave/staff/records?as=Sam%20Lee")
    page.wait_for_url("**period=term**")
    assert "Rejected" in page.url
    # A link naming its own filters shows them and keeps the choice.
    page.goto(ORIGIN + "/ra-leave/staff/records?as=Sam%20Lee&period=whole")
    expect(page.locator("#period")).to_have_value("whole")
    page.goto(ORIGIN + "/ra-leave/staff/records?as=Sam%20Lee")
    page.wait_for_url("**period=term**")
    # Another viewer keeps their own.
    page.goto(ORIGIN + "/ra-leave/staff/records")
    expect(page.locator("#period")).to_have_value("week")
